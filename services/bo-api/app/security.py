"""Authentification des opérateurs du back-office.

Deux contrôles à chaque requête :
1. le JWT est vérifié localement (signature RS256, audience `orbe-bo`, type `operator`) ;
2. la session est confirmée auprès d'auth-service (`GET /operators/me`) : déconnexion,
   expiration ou compte désactivé sont pris en compte. Ce résultat est mis en cache quelques
   secondes par session pour ne pas solliciter auth-service à chaque rafraîchissement.

bo-api n'a pas accès à la base : il ne connaît de l'opérateur que ce que renvoie auth-service.
"""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.errors import error, unauthorized, upstream_unavailable
from app.logging_setup import log_event
from app.metrics import UPSTREAM_ERRORS

bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger("security")

ROLES = ("viewer", "operator")  # du moins au plus privilégié


class TokenVerifier:
    """Vérifie localement les JWT RS256 émis par auth-service."""

    def __init__(self, public_key: RSAPublicKey, issuer: str, audience: str) -> None:
        self._public_key = public_key
        self._issuer = issuer
        self._audience = audience

    @classmethod
    def from_pem_file(cls, path: Path, issuer: str, audience: str) -> "TokenVerifier":
        key = serialization.load_pem_public_key(path.read_bytes())
        if not isinstance(key, RSAPublicKey):
            raise ValueError("La clé JWT doit être une clé publique RSA")
        return cls(key, issuer, audience)

    def decode(self, token: str) -> dict[str, Any]:
        claims = jwt.decode(
            token,
            self._public_key,
            algorithms=["RS256"],
            audience=self._audience,
            issuer=self._issuer,
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
        if claims.get("typ") != "operator":
            raise jwt.InvalidTokenError("jeton qui n'est pas un jeton opérateur")
        return claims


@dataclass(frozen=True)
class Operator:
    """Opérateur authentifié ; le rôle vient d'auth-service, pas du jeton (il peut changer)."""

    operator_id: str
    email: str
    display_name: str
    role: str
    session_id: str

    def has_role(self, role: str) -> bool:
        return ROLES.index(self.role) >= ROLES.index(role)


class OperatorSessions:
    """Confirme la session auprès d'auth-service, avec un cache court par session."""

    def __init__(self, http: httpx.AsyncClient, auth_url: str, ttl_seconds: float) -> None:
        self._http = http
        self._url = f"{auth_url}/operators/me"
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[float, Operator | None]] = {}
        self._max = 1_000

    def forget(self, session_id: str) -> None:
        self._cache.pop(session_id, None)

    async def resolve(self, token: str, session_id: str) -> Operator | None:
        now = time.monotonic()
        cached = self._cache.get(session_id)
        if cached and cached[0] > now:
            return cached[1]
        try:
            response = await self._http.get(self._url, headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError:
            UPSTREAM_ERRORS.labels(upstream="auth").inc()
            log_event(logger, "auth_unreachable", level=logging.WARNING)
            raise upstream_unavailable("auth") from None
        if response.status_code == 401:
            operator = None
        elif response.status_code == 200:
            body = response.json()
            operator = Operator(
                operator_id=body["operator_id"],
                email=body["email"],
                display_name=body["display_name"],
                role=body["role"],
                session_id=body["session_id"],
            )
        else:
            UPSTREAM_ERRORS.labels(upstream="auth").inc()
            raise upstream_unavailable("auth")
        if len(self._cache) >= self._max:
            self._cache.clear()
        self._cache[session_id] = (now + self._ttl, operator)
        return operator


async def current_operator(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
) -> Operator:
    if credentials is None:
        raise unauthorized()
    state = request.app.state
    try:
        claims = state.tokens.decode(credentials.credentials)
    except jwt.PyJWTError:
        raise unauthorized() from None
    operator = await state.operator_sessions.resolve(credentials.credentials, claims["jti"])
    if operator is None or operator.operator_id != claims["sub"]:
        raise unauthorized()
    return operator


def require_role(role: str):
    """Dépendance : l'opérateur doit avoir au moins ce rôle (viewer < operator)."""

    async def check(operator: Operator = Depends(current_operator)) -> Operator:
        if not operator.has_role(role):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=error("forbidden", "Action réservée au rôle « opérateur »."),
            )
        return operator

    return check
