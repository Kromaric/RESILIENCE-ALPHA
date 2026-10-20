"""Sessions et applications clientes (CADRAGE §4.2, docs/mcd.md)."""

import uuid
from datetime import timedelta
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, utcnow
from app.models import Client, ClientApi, Session
from app.schemas import TokenResponse, error
from app.security import hash_api_key

bearer = HTTPBearer(auto_error=False)

INVALID_SESSION = error("invalid_token", "Session invalide ou expirée.")
INVALID_CLIENT = error("invalid_client", "Application cliente inconnue ou non autorisée.")


def unauthorized(detail: dict[str, str] = INVALID_SESSION) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


async def resolve_client_api(db: AsyncSession, client_id: str, api_key: str | None) -> ClientApi:
    """L'appli web est publique (pas de secret dans un navigateur) ; les partenaires et
    services (sonde) doivent présenter leur clé d'API."""
    api = await db.get(ClientApi, client_id)
    if api is None or not api.active:
        raise unauthorized(INVALID_CLIENT)
    if api.key_hash is not None and (api_key is None or hash_api_key(api_key) != api.key_hash):
        raise unauthorized(INVALID_CLIENT)
    return api


async def open_session(
    db: AsyncSession,
    client: Client,
    api: ClientApi,
    *,
    status_: str,
    factors: list[str],
    ttl_seconds: int,
    ip: str | None,
    challenge: str | None = None,
) -> Session:
    now = utcnow()
    session = Session(
        id=str(uuid.uuid4()),
        client_id=client.id,
        client_api_id=api.id,
        status=status_,
        factors=",".join(factors),
        webauthn_challenge=challenge,
        challenge_purpose="login" if challenge else None,
        ip_address=ip,
        opened_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db.add(session)
    await db.commit()
    return session


def token_for(request: Request, client: Client, session: Session, api: ClientApi) -> TokenResponse:
    tokens = request.app.state.tokens
    return TokenResponse(
        access_token=tokens.issue(
            client.id,
            client.email,
            session_id=session.id,
            factors=session.factor_list,
            client_api_id=api.id,
            client_api_type=api.type,
        ),
        expires_in=tokens.ttl,
        factors=session.factor_list,
    )


async def current_session(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_session),
) -> tuple[dict[str, Any], Session]:
    """JWT valide **et** session active en base : une session révoquée est refusée."""
    if credentials is None:
        raise unauthorized()
    try:
        claims = request.app.state.tokens.decode(credentials.credentials)
    except jwt.PyJWTError:
        raise unauthorized() from None
    session = await db.get(Session, claims.get("jti"))
    if session is None or session.client_id != claims["sub"] or session.status != "active":
        raise unauthorized()
    if session.expires_at <= utcnow():
        await db.execute(update(Session).where(Session.id == session.id).values(status="expired"))
        await db.commit()
        raise unauthorized()
    return claims, session
