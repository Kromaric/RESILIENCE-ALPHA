import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.config import Settings
from app.db import make_engine
from app.logging_setup import configure_logging, log_event, request_id_var
from app.ratelimit import SlidingWindowLimiter
from app.routes import auth, health
from app.routes.auth import client_ip
from app.security import PasswordVerifier, TokenService

logger = logging.getLogger("http")
QUIET_PATHS = {"/metrics", "/health/live", "/health/ready"}


def create_app(settings: Settings | None = None, engine: AsyncEngine | None = None) -> FastAPI:
    """Fabrique de l'application (uvicorn app.main:create_app --factory)."""
    settings = settings or Settings()
    configure_logging(settings.service_name, settings.log_level)
    engine = engine or make_engine(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log_event(logging.getLogger("app"), "service_started")
        yield
        await engine.dispose()

    app = FastAPI(
        title="Orbe — auth-service",
        version="0.1.0",
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
    app.state.passwords = PasswordVerifier(settings.hash_concurrency)
    app.state.login_limiter = SlidingWindowLimiter(settings.login_rate_per_ip)

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
    app.include_router(health.router)

    Instrumentator(excluded_handlers=["/metrics", "/health/.*"]).instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )
    return app
