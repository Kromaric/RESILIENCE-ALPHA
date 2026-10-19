import logging
from datetime import timedelta
from typing import Any

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, utcnow
from app.logging_setup import log_event
from app.metrics import ACCOUNT_LOCKS, API_KEY_FAILURES, LOGIN_FAILURES, LOGINS
from app.models import ApiKey, Client
from app.schemas import (
    ErrorOut,
    LoginRequest,
    MeResponse,
    TokenResponse,
    VerifyResponse,
    error,
)
from app.security import hash_api_key, mask_phone, normalize_email

router = APIRouter()
logger = logging.getLogger("auth")
bearer = HTTPBearer(auto_error=False)

INVALID_CREDENTIALS = error("invalid_credentials", "Email ou mot de passe incorrect.")


def client_ip(request: Request) -> str:
    """IP d'origine transmise par le WAF (seul point d'entrée, CADRAGE §4.1)."""
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "-")


async def register_failure(session: AsyncSession, client_id: str, request: Request) -> None:
    settings = request.app.state.settings
    reaches_threshold = Client.failed_logins + 1 >= settings.lockout_threshold
    lock_until = utcnow() + timedelta(minutes=settings.lockout_minutes)
    # Une seule requête atomique. locked_until est assigné avant failed_logins :
    # MariaDB évalue les affectations de gauche à droite.
    await session.execute(
        update(Client)
        .where(Client.id == client_id)
        .ordered_values(
            (Client.locked_until, case((reaches_threshold, lock_until), else_=Client.locked_until)),
            (Client.failed_logins, case((reaches_threshold, 0), else_=Client.failed_logins + 1)),
        )
    )
    await session.commit()


@router.post(
    "/login",
    response_model=TokenResponse,
    tags=["Authentification"],
    summary="Se connecter",
    responses={
        401: {"model": ErrorOut, "description": "Email ou mot de passe incorrect"},
        423: {"model": ErrorOut, "description": "Compte bloqué (en-tête Retry-After)"},
        429: {"model": ErrorOut, "description": "Trop de tentatives depuis cette IP"},
    },
)
async def login(
    body: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    state = request.app.state
    ip = client_ip(request)

    if not state.login_limiter.allow(ip):
        LOGIN_FAILURES.labels(reason="rate_limited").inc()
        log_event(logger, "login_failed", reason="rate_limited", client_ip=ip)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error("too_many_attempts", "Trop de tentatives. Réessayez dans une minute."),
            headers={"Retry-After": "60"},
        )

    email = normalize_email(body.email)
    client = (
        await session.execute(select(Client).where(Client.email == email))
    ).scalar_one_or_none()

    now = utcnow()
    if client and client.locked_until and client.locked_until > now:
        retry_after = int((client.locked_until - now).total_seconds()) + 1
        LOGIN_FAILURES.labels(reason="locked").inc()
        log_event(logger, "login_failed", reason="locked", client_id=client.id, client_ip=ip)
        raise HTTPException(
            status.HTTP_423_LOCKED,
            detail=error("account_locked", "Compte bloqué temporairement après trop d'échecs."),
            headers={"Retry-After": str(retry_after)},
        )

    if not await state.passwords.verify(client.password_hash if client else None, body.password):
        if client:
            will_lock = client.failed_logins + 1 >= state.settings.lockout_threshold
            await register_failure(session, client.id, request)
            if will_lock:
                ACCOUNT_LOCKS.inc()
                log_event(logger, "account_locked", client_id=client.id, client_ip=ip)
        LOGIN_FAILURES.labels(reason="invalid_credentials").inc()
        log_event(
            logger,
            "login_failed",
            reason="invalid_credentials",
            client_id=client.id if client else None,
            client_ip=ip,
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)

    if client.failed_logins or client.locked_until:
        await session.execute(
            update(Client).where(Client.id == client.id).values(failed_logins=0, locked_until=None)
        )
        await session.commit()

    LOGINS.inc()
    log_event(logger, "login_succeeded", client_id=client.id, client_ip=ip)
    return TokenResponse(
        access_token=state.tokens.issue(client.id, client.email),
        expires_in=state.tokens.ttl,
    )


async def current_claims(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
) -> dict[str, Any]:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail=error("invalid_token", "Session invalide ou expirée."),
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        return request.app.state.tokens.decode(credentials.credentials)
    except jwt.PyJWTError:
        raise unauthorized from None


@router.get(
    "/me",
    response_model=MeResponse,
    tags=["Authentification"],
    summary="Mon profil",
    responses={401: {"model": ErrorOut, "description": "Jeton absent, invalide ou expiré"}},
)
async def me(
    claims: dict[str, Any] = Depends(current_claims),
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    client = await session.get(Client, claims["sub"])
    if client is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail=error("invalid_token", "Session invalide ou expirée."),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return MeResponse(
        client_id=client.id,
        email=client.email,
        phone_masked=mask_phone(client.phone),
        display_name=client.display_name,
    )


@router.get(
    "/verify",
    response_model=VerifyResponse,
    tags=["Partenaires"],
    summary="Vérifier une clé d'API partenaire",
    responses={401: {"model": ErrorOut, "description": "Clé absente, inconnue ou désactivée"}},
)
async def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    session: AsyncSession = Depends(get_session),
) -> VerifyResponse:
    key = None
    if x_api_key:
        key = (
            await session.execute(
                select(ApiKey).where(
                    ApiKey.key_hash == hash_api_key(x_api_key), ApiKey.active.is_(True)
                )
            )
        ).scalar_one_or_none()
    if key is None:
        API_KEY_FAILURES.inc()
        log_event(logger, "api_key_rejected", client_ip=client_ip(request))
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail=error("invalid_api_key", "Clé d'API invalide.")
        )
    return VerifyResponse(partner=key.partner_name, scopes=key.scopes)
