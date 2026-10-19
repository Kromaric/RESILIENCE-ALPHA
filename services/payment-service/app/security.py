import hashlib
import json
import secrets
import uuid
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from fastapi import Depends, Header, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.errors import api_error

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


async def current_client_id(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
) -> str:
    unauthorized = api_error(
        status.HTTP_401_UNAUTHORIZED,
        "invalid_token",
        "Session invalide ou expirée.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        return request.app.state.tokens.decode(credentials.credentials)["sub"]
    except jwt.PyJWTError:
        raise unauthorized from None


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
