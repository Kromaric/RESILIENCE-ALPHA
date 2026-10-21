import asyncio
import hashlib
import re
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

    async def hash_async(self, password: str) -> str:
        """Hachage borné par le même sémaphore : une rafale d'inscriptions ne sature pas la RAM."""
        async with self._semaphore:
            return await run_in_threadpool(self._hasher.hash, password)

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

    def issue(
        self,
        client_id: str,
        email: str,
        *,
        session_id: str | None = None,
        factors: list[str] | None = None,
        client_api_id: str = "orbe-web",
        client_api_type: str = "application",
    ) -> str:
        """JWT de session : `jti` = identifiant de session, `amr` = facteurs utilisés,
        `cid` / `cty` = application cliente et son type (payment-service s'en sert)."""
        now = int(time.time())
        payload = {
            "sub": client_id,
            "email": email,
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "nbf": now,
            "exp": now + self.ttl,
            "jti": session_id or str(uuid.uuid4()),
            "amr": factors or ["pwd"],
            "cid": client_api_id,
            "cty": client_api_type,
        }
        return jwt.encode(payload, self._private_key, algorithm=self.algorithm)

    def issue_operator(self, operator_id: str, email: str, role: str, session_id: str) -> str:
        """JWT du back-office : `role` (viewer | operator), mot de passe seul."""
        now = int(time.time())
        payload = {
            "sub": operator_id,
            "email": email,
            "role": role,
            "typ": "operator",
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "nbf": now,
            "exp": now + self.ttl,
            "jti": session_id,
            "amr": ["pwd"],
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


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_SEPARATORS = re.compile(r"[\s.\-()]")


def valid_email(email: str) -> bool:
    return bool(_EMAIL.fullmatch(email)) and len(email) <= 254


def normalize_phone(raw: str) -> str | None:
    """Téléphone au format E.164 ; mêmes règles que la désignation d'un bénéficiaire
    (payment-service) : '06 12 34 56 78' et '0033 6 12 34 56 78' → '+33612345678'."""
    digits = _PHONE_SEPARATORS.sub("", raw.strip())
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if re.fullmatch(r"0[1-9]\d{8}", digits):
        return "+33" + digits[1:]
    if re.fullmatch(r"\+[1-9]\d{7,14}", digits):
        return digits
    return None


# Extrait des mots de passe les plus utilisés (listes publiques de fuites) ; comparaison
# insensible à la casse
COMMON_PASSWORDS = {
    "12345678",
    "password",
    "azertyui",
    "motdepasse",
    "123456789012",
    "1234567890ab",
    "azertyuiop12",
    "azertyuiopqs",
    "qwertyuiop12",
    "motdepasse12",
    "motdepasse123",
    "password1234",
    "password12345",
    "passwordpassword",
    "000000000000",
    "111111111111",
    "aaaaaaaaaaaa",
    "iloveyou1234",
    "bonjour12345",
    "soleil123456",
    "orbeorbeorbe",
    "orbe12345678",
    "demo-password",
    "changeme1234",
    "administrateur",
    "welcome12345",
    "qwerty123456",
    "azerty123456",
    "1q2w3e4r5t6y",
}


def password_problem(password: str, email: str) -> str | None:
    """Message d'erreur si le mot de passe est trop faible, sinon None."""
    if len(password) < 8:
        return "8 caractères minimum."
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS or len(set(lowered)) < 4:
        return "Mot de passe trop courant ou trop simple."
    local_part = email.split("@", 1)[0].lower()
    if len(local_part) >= 4 and local_part in lowered:
        return "Le mot de passe ne doit pas contenir votre adresse email."
    return None
