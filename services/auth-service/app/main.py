import asyncio
import contextlib
import logging
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app import led
from app.config import Settings
from app.db import make_engine
from app.face.cipher import LocalCipher, VaultTransitCipher
from app.face.engine import FakeFaceEngine, InsightFaceEngine
from app.logging_setup import configure_logging, log_event, request_id_var
from app.ratelimit import SlidingWindowLimiter
from app.routes import auth, face, health, operator_admin, operators
from app.routes.auth import client_ip
from app.security import PasswordVerifier, TokenService
from app.vault import SecretNotFound

logger = logging.getLogger("http")
QUIET_PATHS = {"/metrics", "/health/live", "/health/ready"}


def create_app(settings: Settings | None = None, engine: AsyncEngine | None = None) -> FastAPI:
    """Fabrique de l'application (uvicorn app.main:create_app --factory)."""
    settings = settings or Settings()
    configure_logging(settings.service_name, settings.log_level)
    engine = engine or make_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log_event(logging.getLogger("app"), "service_started", face_engine=face_engine.model_name)
        warm_up = None
        if hasattr(face_engine, "warm_up"):
            # Chargement du modèle en arrière-plan : le service démarre sans attendre
            warm_up = asyncio.create_task(face_engine.warm_up())
        yield
        if warm_up is not None and not warm_up.done():
            warm_up.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await warm_up
        await engine.dispose()

    app = FastAPI(
        title="Orbe — auth-service",
        version="0.1.0",
        description=(
            "Authentification forte des clients Orbe : mot de passe puis **reconnaissance "
            "faciale** (modèle InsightFace, test du vivant par rotation de la tête dans un sens "
            "tiré au hasard), sessions révocables (JWT RS256 de 15 min), "
            "applications clientes et clés d'API partenaires. Exposé par le WAF sous `/api/auth`. "
            'Erreurs : `{"detail": {"code", "message"}}`. Voir CADRAGE §4.2.'
        ),
        openapi_tags=[
            {
                "name": "Authentification",
                "description": "Connexion en deux étapes (mot de passe, puis visage) et profil",
            },
            {
                "name": "Visage",
                "description": "Enrôlement et effacement du visage (consentement, RGPD art. 9)",
            },
            {"name": "Partenaires", "description": "Clés d'API des partenaires"},
            {
                "name": "Back-office",
                "description": "Connexion des opérateurs du dashboard (mot de passe seul)",
            },
        ],
        lifespan=lifespan,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
    )

    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    app.state.tokens = TokenService.from_pem_file(
        settings.jwt_private_key_file,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        ttl=settings.jwt_ttl_seconds,
    )
    app.state.operator_tokens = TokenService.from_pem_file(
        settings.jwt_private_key_file,
        issuer=settings.jwt_issuer,
        audience=settings.bo_jwt_audience,
        ttl=settings.bo_jwt_ttl_seconds,
    )
    app.state.led = led.LedController(settings.led_blink_period_ms)
    try:
        app.state.led_device_key = settings.secret(
            settings.led_device_key_name, settings.led_device_key_file
        )
    except SecretNotFound:
        app.state.led_device_key = None  # GET /devices/led refuse alors toute demande
    app.state.passwords = PasswordVerifier(settings.hash_concurrency)
    app.state.login_limiter = SlidingWindowLimiter(settings.login_rate_per_ip)
    app.state.register_limiter = SlidingWindowLimiter(settings.register_rate_per_ip)
    face_engine = (
        FakeFaceEngine()
        if settings.face_engine == "fake"
        else InsightFaceEngine(
            settings.face_model, settings.face_model_root, settings.face_det_size
        )
    )
    app.state.face_engine = face_engine
    if settings.face_cipher == "vault":
        app.state.face_cipher = VaultTransitCipher(
            httpx.AsyncClient(base_url=settings.vault_addr, timeout=5),
            settings.vault_transit_key,
            settings.vault_token_file.read_text(encoding="utf-8").strip(),
        )
    else:
        app.state.face_cipher = LocalCipher.from_hex(
            settings.secret(settings.face_key_name, settings.face_key_file)
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Format d'erreur commun ; la valeur reçue (« input ») n'est jamais renvoyée :
        # elle peut contenir un mot de passe
        fields = [
            {"field": ".".join(str(part) for part in err["loc"][1:]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "validation_error",
                    "message": "Requête invalide.",
                    "fields": fields,
                }
            },
        )

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            if request.url.path not in QUIET_PATHS:
                log_event(
                    logger,
                    "request",
                    method=request.method,
                    path=request.url.path,
                    status=status_code,
                    duration_ms=round((time.perf_counter() - start) * 1000, 1),
                    client_ip=client_ip(request),
                )
            request_id_var.reset(token)

    app.include_router(auth.router)
    app.include_router(face.router)
    app.include_router(operators.router)
    app.include_router(operator_admin.router)
    app.include_router(led.router)
    app.include_router(health.router)

    Instrumentator(excluded_handlers=["/metrics", "/health/.*"]).instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )
    return app
