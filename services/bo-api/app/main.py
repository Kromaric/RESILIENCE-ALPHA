import logging
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.config import Settings
from app.db import make_engine
from app.errors import error
from app.logging_setup import configure_logging, log_event, request_id_var
from app.ratelimit import SlidingWindowLimiter
from app.routes import auth, control, data, health, supervision
from app.routes.auth import client_ip
from app.security import OperatorSessions, TokenVerifier
from app.upstream import ControlPlane, Loki, Prometheus

logger = logging.getLogger("http")
QUIET_PATHS = {"/metrics", "/health/live", "/health/ready"}


def create_app(
    settings: Settings | None = None,
    http: httpx.AsyncClient | None = None,
    engine: AsyncEngine | None = None,
) -> FastAPI:
    """Fabrique de l'application (uvicorn app.main:create_app --factory)."""
    settings = settings or Settings()
    configure_logging(settings.service_name, settings.log_level)
    http = http or httpx.AsyncClient(timeout=settings.upstream_timeout_seconds)
    engine = engine or make_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log_event(logging.getLogger("app"), "service_started")
        yield
        await http.aclose()
        await engine.dispose()

    app = FastAPI(
        title="Orbe — bo-api",
        version="0.1.0",
        description=(
            "API du back-office : alimente le dashboard de supervision (état des services, "
            "indicateurs, incidents, journaux, Grafana, assistant). **Lecture seule** : aucune "
            "route ne modifie la plateforme.\n\n"
            "- Connexion : `POST /bo/auth/login` (opérateur, mot de passe seul), puis "
            "`Authorization: Bearer <jeton>` sur toutes les autres routes.\n"
            "- Rôles : `viewer` (indicateurs agrégés) et `operator` (en plus : listes et fiches "
            "clients, opérations, demandes ; chaque consultation est journalisée).\n"
            '- Erreurs : `{"detail": {"code", "message"}}` ; un service interrogé '
            "indisponible renvoie `503 <service>_unavailable`.\n\n"
            "Voir CADRAGE §4.7."
        ),
        openapi_tags=[
            {"name": "Connexion", "description": "Connexion des opérateurs"},
            {
                "name": "Supervision",
                "description": "État des services, indicateurs, courbes, ressources, journaux",
            },
            {
                "name": "Données applicatives",
                "description": "Clients, opérations, demandes et comptabilité (lecture seule, "
                "email et téléphone masqués)",
            },
        ],
        lifespan=lifespan,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
    )

    app.state.settings = settings
    app.state.http = http
    app.state.engine = engine
    app.state.sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    app.state.tokens = TokenVerifier.from_pem_file(
        settings.jwt_public_key_file, issuer=settings.jwt_issuer, audience=settings.jwt_audience
    )
    app.state.prometheus = Prometheus(http, settings.prometheus_url)
    app.state.loki = Loki(http, settings.loki_url)
    app.state.control_plane = ControlPlane(http, settings)
    app.state.ask_limiter = SlidingWindowLimiter(settings.assistant_rate_per_operator)
    app.state.operator_sessions = OperatorSessions(
        http, settings.auth_url, settings.session_cache_seconds
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Ne renvoie jamais la valeur reçue (« input ») : elle peut contenir un mot de passe
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

    @app.exception_handler(sa_exc.OperationalError)
    @app.exception_handler(sa_exc.InterfaceError)
    @app.exception_handler(sa_exc.TimeoutError)
    async def database_down(request: Request, exc: Exception) -> JSONResponse:
        log_event(logger, "db_unavailable", level=logging.ERROR, path=request.url.path)
        return JSONResponse(
            status_code=503,
            content={
                "detail": error(
                    "database_unavailable", "Base de données momentanément indisponible."
                )
            },
            headers={"Retry-After": "5"},
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
    app.include_router(supervision.router)
    app.include_router(data.router)
    app.include_router(control.router)
    app.include_router(health.router)

    Instrumentator(excluded_handlers=["/metrics", "/health/.*"]).instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )
    return app
