import hashlib
import json
import secrets
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from fastapi import Depends, Header, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.db import utcnow
from app.errors import api_error
from app.models import Session

bearer = HTTPBearer(auto_error=False)


class TokenVerifier:
    """Vérifie localement les JWT RS256 émis par auth-service (pas d'appel réseau)."""

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
        return jwt.decode(
            token,
            self._public_key,
            algorithms=["RS256"],
            audience=self._audience,
            issuer=self._issuer,
            options={"require": ["exp", "iat", "sub"]},
        )


@dataclass(frozen=True)
class Principal:
    """Client authentifié et contexte de sa session (claims du JWT)."""

    client_id: str
    session_id: str
    factors: tuple[str, ...]
    client_api_id: str
    client_api_type: str

    @property
    def strong(self) -> bool:
        """Session confirmée par passkey, ou service technique (sonde)."""
        return "passkey" in self.factors or self.client_api_type == "service"


class SessionGuard:
    """Vérifie en base que la session du JWT est active (non révoquée, non expirée).

    Le résultat est mis en cache quelques secondes par session : on ne consomme pas une
    connexion du pool à chaque requête (ressource critique du scénario SC-01), au prix
    d'un délai maximal de prise en compte d'une révocation.
    """

    def __init__(self, sessionmaker, ttl_seconds: float, max_entries: int = 10_000) -> None:
        self._sessionmaker = sessionmaker
        self._ttl = ttl_seconds
        self._max = max_entries
        self._cache: dict[str, tuple[float, bool]] = {}

    async def is_active(self, session_id: str, client_id: str) -> bool:
        now = time.monotonic()
        cached = self._cache.get(session_id)
        if cached and cached[0] > now:
            return cached[1]
        async with self._sessionmaker() as db:
            row = (
                await db.execute(
                    select(Session.status, Session.client_id, Session.expires_at).where(
                        Session.id == session_id
                    )
                )
            ).first()
        active = bool(
            row
            and row.status == "active"
            and row.client_id == client_id
            and row.expires_at > utcnow()
        )
        if len(self._cache) >= self._max:
            self._cache = {k: v for k, v in self._cache.items() if v[0] > now}
        self._cache[session_id] = (now + self._ttl, active)
        return active


def _unauthorized():
    return api_error(
        status.HTTP_401_UNAUTHORIZED,
        "invalid_token",
        "Session invalide ou expirée.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def current_principal(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
) -> Principal:
    if credentials is None:
        raise _unauthorized()
    try:
        claims = request.app.state.tokens.decode(credentials.credentials)
    except jwt.PyJWTError:
        raise _unauthorized() from None
    session_id = claims.get("jti")
    if not session_id or not await request.app.state.sessions.is_active(session_id, claims["sub"]):
        raise _unauthorized()
    return Principal(
        client_id=claims["sub"],
        session_id=session_id,
        factors=tuple(claims.get("amr") or ()),
        client_api_id=claims.get("cid", "orbe-web"),
        client_api_type=claims.get("cty", "application"),
    )


async def strong_principal(principal: Principal = Depends(current_principal)) -> Principal:
    """Déplacer de l'argent exige une session confirmée par passkey (CADRAGE §4.2)."""
    if not principal.strong:
        raise api_error(
            status.HTTP_403_FORBIDDEN,
            "second_factor_required",
            "Confirmez votre identité avec votre passkey (Face ID, Windows Hello).",
        )
    return principal


async def current_client_id(principal: Principal = Depends(current_principal)) -> str:
    return principal.client_id


async def idempotency_key(
    value: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str:
    """En-tête obligatoire sur toute opération qui crée de l'argent ou en déplace."""
    if not value:
        raise api_error(400, "idempotency_key_required", "En-tête Idempotency-Key obligatoire.")
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise api_error(
            400, "invalid_idempotency_key", "Idempotency-Key doit être un UUID."
        ) from None


def fingerprint(payload: dict[str, Any]) -> str:
    """Empreinte d'une requête pour détecter la réutilisation d'une clé avec un autre corps.

    Ne jamais y mettre le numéro de carte ni le CVC.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def new_reference(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(4)}"


def new_qr_token() -> str:
    return secrets.token_urlsafe(16)  # 22 caractères
