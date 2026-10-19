import asyncio
import hashlib
import time
import uuid
from pathlib import Path
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from starlette.concurrency import run_in_threadpool


class PasswordVerifier:
    """Vérification argon2id bornée en concurrence.

    Paramètres OWASP minimaux (19 Mio, 2 itérations) : sous une rafale de connexions,
    la mémoire consommée reste bornée à hash_concurrency × 19 Mio.
    """

    def __init__(self, concurrency: int) -> None:
        self._hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
        self._semaphore = asyncio.Semaphore(concurrency)
        # Vérifié quand l'email est inconnu, pour ne pas révéler son absence par le temps de réponse
        self._dummy_hash = self._hasher.hash("orbe-dummy-password")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def _verify_sync(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    async def verify(self, password_hash: str | None, password: str) -> bool:
        async with self._semaphore:
            ok = await run_in_threadpool(
                self._verify_sync, password_hash or self._dummy_hash, password
            )
        return ok and password_hash is not None


class TokenService:
    """Émission et vérification des JWT RS256."""

    algorithm = "RS256"

    def __init__(self, private_key: RSAPrivateKey, issuer: str, audience: str, ttl: int) -> None:
        self._private_key = private_key
        self._public_key = private_key.public_key()
        self._issuer = issuer
        self._audience = audience
        self.ttl = ttl

    @classmethod
    def from_pem_file(cls, path: Path, issuer: str, audience: str, ttl: int) -> "TokenService":
        key = serialization.load_pem_private_key(path.read_bytes(), password=None)
        if not isinstance(key, RSAPrivateKey):
            raise ValueError("La clé JWT doit être une clé privée RSA")
        return cls(key, issuer, audience, ttl)

    def issue(self, client_id: str, email: str) -> str:
        now = int(time.time())
        payload = {
            "sub": client_id,
            "email": email,
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "nbf": now,
            "exp": now + self.ttl,
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(payload, self._private_key, algorithm=self.algorithm)

    def decode(self, token: str) -> dict[str, Any]:
        return jwt.decode(
            token,
            self._public_key,
            algorithms=[self.algorithm],
            audience=self._audience,
            issuer=self._issuer,
            options={"require": ["exp", "iat", "sub"]},
        )


def hash_api_key(api_key: str) -> str:
    """Les clés d'API sont longues et aléatoires : un SHA-256 suffit (pas de dictionnaire)."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def mask_phone(phone: str) -> str:
    """+33612345678 → '+33 6 •• •• •• 78'."""
    if phone.startswith("+33") and len(phone) == 12:
        return f"+33 {phone[3]} •• •• •• {phone[-2:]}"
    return f"{phone[:3]} •••• {phone[-2:]}"
