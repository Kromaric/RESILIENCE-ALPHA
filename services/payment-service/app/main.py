import asyncio
import contextlib
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.config import Settings
from app.consistency import reconcile_forever
from app.db import make_engine
from app.logging_setup import configure_logging, log_event, request_id_var
from app.metrics import DB_ERRORS, POOL_TIMEOUTS, bind_pool_metrics
from app.payments import SimulatedAuthorizer
from app.ratelimit import SlidingWindowLimiter
from app.routes import health, payments
from app.security import SessionGuard, TokenVerifier

logger = logging.getLogger("http")
QUIET_PATHS = {"/metrics", "/health/live", "/health/ready"}


def client_ip(request: Request) -> str:
    """IP d'origine transmise par le WAF (seul point d'entrée, CADRAGE §4.1)."""
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "-")


def unavailable(code: str) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": {
                "code": code,
                "message": "Service de paiement momentanément indisponible. Réessayez.",
            }
        },
        headers={"Retry-After": "2"},
    )


def create_app(settings: Settings | None = None, engine: AsyncEngine | None = None) -> FastAPI:
    """Fabrique de l'application (uvicorn app.main:create_app --factory)."""
    settings = settings or Settings()
    configure_logging(settings.service_name, settings.log_level)
    engine = engine or make_engine(settings)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log_event(logging.getLogger("app"), "service_started")
        task = None
        if settings.reconcile_enabled:
            task = asyncio.create_task(
                reconcile_forever(
                    sessionmaker,
                    settings.reconcile_after_seconds,
                    settings.reconcile_interval_seconds,
                )
            )
        yield
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await engine.dispose()

    app = FastAPI(
        title="Orbe — payment-service",
        version="0.1.0",
        description=(
            "Paiements entre clients Orbe : transferts payés par carte de test, demandes "
            "d'argent, QR code, remboursements, solde et retraits fictifs. Exposé par le WAF "
            "sous `/api/payments`.\n\n"
            "- Authentification : `Authorization: Bearer <JWT>` obtenu sur auth-service ; la "
            "session ne doit pas être révoquée. Déplacer de l'argent exige une session confirmée "
            "par reconnaissance faciale (`403 second_factor_required` sinon).\n"
            "- Opérations qui déplacent de l'argent : en-tête `Idempotency-Key` (UUID) "
            "obligatoire ; `201` à la création, `200` si la même clé est rejouée.\n"
            "- Un refus de carte n'est pas une erreur HTTP : `201` avec `status: declined`.\n"
            "- Plafond : 500 € par opération. Chaque opération autorisée passe deux écritures "
            "comptables (débit, crédit).\n"
            "- Cartes de test : `4242 4242 4242 4242` (acceptée), `4000 0000 0000 0002` "
            "(refusée), `…0069` (expirée), `…9995` (fonds insuffisants).\n\n"
            "Voir CADRAGE §4.3."
        ),
        openapi_tags=[
            {"name": "Paiements", "description": "Envoyer et rembourser"},
            {"name": "Historique", "description": "Opérations envoyées et reçues"},
            {"name": "Compte", "description": "Solde, comptes liés et retraits"},
            {"name": "Demandes d'argent", "description": "Demander, payer, refuser, annuler"},
            {"name": "QR code", "description": "Recevoir de l'argent par QR code"},
            {"name": "Contacts", "description": "Carnet de contacts (clients Orbe)"},
        ],
        lifespan=lifespan,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
    )

    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker
    app.state.tokens = TokenVerifier.from_pem_file(
        settings.jwt_public_key_file, issuer=settings.jwt_issuer, audience=settings.jwt_audience
    )
    app.state.sessions = SessionGuard(sessionmaker, settings.session_cache_seconds)
    app.state.authorizer = SimulatedAuthorizer(
        settings.authorization_min_ms, settings.authorization_max_ms
    )
    app.state.pay_limiter = (
        SlidingWindowLimiter(settings.pay_rate_per_client) if settings.pay_rate_per_client else None
    )
    bind_pool_metrics(engine.pool)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Ne renvoie jamais la valeur reçue (« input ») : elle peut contenir un numéro de carte
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

    @app.exception_handler(sa_exc.TimeoutError)
    async def pool_exhausted(request: Request, exc: sa_exc.TimeoutError) -> JSONResponse:
        POOL_TIMEOUTS.inc()
        log_event(logger, "db_pool_timeout", level=logging.WARNING, path=request.url.path)
        return unavailable("service_unavailable")

    @app.exception_handler(sa_exc.OperationalError)
    @app.exception_handler(sa_exc.InterfaceError)
    async def database_down(request: Request, exc: sa_exc.DBAPIError) -> JSONResponse:
        DB_ERRORS.inc()
        log_event(logger, "db_unavailable", level=logging.ERROR, path=request.url.path)
        return unavailable("service_unavailable")

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

    app.include_router(payments.router)
    app.include_router(health.router)

    Instrumentator(excluded_handlers=["/metrics", "/health/.*"]).instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )
    return app
