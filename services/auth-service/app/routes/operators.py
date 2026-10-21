"""Connexion des opérateurs du back-office (dashboard) : mot de passe seul.

Comptes et sessions séparés de ceux des clients, JWT d'audience `orbe-bo` : un jeton client
n'ouvre pas le dashboard et un jeton opérateur n'est pas accepté par payment-service.
bo-api valide les jetons et vérifie la session avec `GET /operators/me`.
"""

import logging
import uuid
from datetime import timedelta
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, utcnow
from app.logging_setup import log_event
from app.metrics import ACCOUNT_LOCKS, LOGIN_FAILURES, LOGINS, SESSIONS_REVOKED
from app.models import Operator, OperatorSession
from app.routes.auth import INVALID_CREDENTIALS, client_ip, rate_limit, register_failure
from app.schemas import ErrorOut, LoginRequest, OperatorMe, OperatorTokenResponse, error
from app.security import normalize_email
from app.sessions import bearer, unauthorized

router = APIRouter(prefix="/operators", tags=["Back-office"])
logger = logging.getLogger("operators")


async def current_operator(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_session),
) -> tuple[dict[str, Any], OperatorSession, Operator]:
    """JWT opérateur valide, session active en base et compte toujours actif."""
    if credentials is None:
        raise unauthorized()
    try:
        claims = request.app.state.operator_tokens.decode(credentials.credentials)
    except jwt.PyJWTError:
        raise unauthorized() from None
    if claims.get("typ") != "operator":
        raise unauthorized()
    session = await db.get(OperatorSession, claims.get("jti"))
    if session is None or session.operator_id != claims["sub"] or session.status != "active":
        raise unauthorized()
    if session.expires_at <= utcnow():
        await db.execute(
            update(OperatorSession).where(OperatorSession.id == session.id).values(status="expired")
        )
        await db.commit()
        raise unauthorized()
    operator = await db.get(Operator, session.operator_id)
    if operator is None or not operator.active:
        raise unauthorized()
    return claims, session, operator


@router.post(
    "/login",
    response_model=OperatorTokenResponse,
    summary="Connexion d'un opérateur",
    responses={
        401: {"model": ErrorOut, "description": "Identifiants invalides ou compte désactivé"},
        423: {"model": ErrorOut, "description": "Compte bloqué (en-tête Retry-After)"},
        429: {"model": ErrorOut, "description": "Trop de tentatives depuis cette IP"},
    },
)
async def login(
    body: LoginRequest, request: Request, db: AsyncSession = Depends(get_session)
) -> OperatorTokenResponse:
    """Mêmes protections que la connexion client : 5 échecs → compte bloqué 10 min,
    20 tentatives par minute et par IP. Pas de reconnaissance faciale."""
    state = request.app.state
    settings = state.settings
    ip = client_ip(request)
    rate_limit(request, ip)

    email = normalize_email(body.email)
    operator = (
        await db.execute(select(Operator).where(Operator.email == email))
    ).scalar_one_or_none()

    now = utcnow()
    if operator and operator.locked_until and operator.locked_until > now:
        LOGIN_FAILURES.labels(reason="locked").inc()
        log_event(
            logger, "operator_login_failed", reason="locked", operator_id=operator.id, client_ip=ip
        )
        raise HTTPException(
            status.HTTP_423_LOCKED,
            detail=error("account_locked", "Compte bloqué temporairement après trop d'échecs."),
            headers={"Retry-After": str(int((operator.locked_until - now).total_seconds()) + 1)},
        )

    password_ok = await state.passwords.verify(
        operator.password_hash if operator else None, body.password
    )
    if not password_ok or not operator.active:
        if operator and not password_ok:
            will_lock = operator.failed_logins + 1 >= settings.lockout_threshold
            await register_failure(db, operator.id, request, Operator)
            if will_lock:
                ACCOUNT_LOCKS.inc()
                log_event(logger, "operator_locked", operator_id=operator.id, client_ip=ip)
        reason = "invalid_credentials" if not password_ok else "inactive"
        LOGIN_FAILURES.labels(reason=reason).inc()
        log_event(
            logger,
            "operator_login_failed",
            reason=reason,
            operator_id=operator.id if operator else None,
            client_ip=ip,
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS)

    tokens = state.operator_tokens
    session = OperatorSession(
        id=str(uuid.uuid4()),
        operator_id=operator.id,
        status="active",
        ip_address=ip,
        opened_at=now,
        expires_at=now + timedelta(seconds=tokens.ttl),
    )
    db.add(session)
    await db.execute(
        update(Operator)
        .where(Operator.id == operator.id)
        .values(failed_logins=0, locked_until=None, last_login_at=now)
    )
    await db.commit()
    LOGINS.inc()
    log_event(
        logger,
        "operator_login_succeeded",
        operator_id=operator.id,
        role=operator.role,
        client_ip=ip,
    )
    return OperatorTokenResponse(
        access_token=tokens.issue_operator(operator.id, operator.email, operator.role, session.id),
        expires_in=tokens.ttl,
        role=operator.role,
    )


@router.post(
    "/logout",
    status_code=204,
    summary="Déconnexion d'un opérateur (révoque la session)",
    responses={401: {"model": ErrorOut, "description": "Session invalide ou expirée"}},
)
async def logout(
    current: tuple[dict[str, Any], OperatorSession, Operator] = Depends(current_operator),
    db: AsyncSession = Depends(get_session),
) -> Response:
    _, session, operator = current
    await db.execute(
        update(OperatorSession)
        .where(OperatorSession.id == session.id)
        .values(status="revoked", revoked_at=utcnow(), revocation_reason="logout")
    )
    await db.commit()
    SESSIONS_REVOKED.labels(reason="operator_logout").inc()
    log_event(logger, "operator_session_revoked", reason="logout", operator_id=operator.id)
    return Response(status_code=204)


@router.get(
    "/me",
    response_model=OperatorMe,
    summary="Opérateur connecté (sert aussi à bo-api pour vérifier la session)",
    responses={401: {"model": ErrorOut, "description": "Jeton absent, invalide ou révoqué"}},
)
async def me(
    current: tuple[dict[str, Any], OperatorSession, Operator] = Depends(current_operator),
) -> OperatorMe:
    _, session, operator = current
    return OperatorMe(
        operator_id=operator.id,
        email=operator.email,
        display_name=operator.display_name,
        role=operator.role,
        session_id=session.id,
        expires_at=session.expires_at.isoformat(timespec="seconds") + "Z",
    )
