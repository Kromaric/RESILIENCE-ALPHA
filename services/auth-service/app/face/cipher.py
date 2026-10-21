"""Chiffrement des gabarits faciaux (embeddings) : jamais de vecteur en clair en base.

Le texte chiffré est **lié à son titulaire** : un gabarit copié sur la ligne d'un autre client
ne se déchiffre pas (données associées AES-GCM, ou contexte de dérivation Vault).

- LocalCipher : AES-256-GCM, clé dans un secret Docker (« local:v1:… »).
- VaultTransitCipher : la clé ne quitte jamais Vault, clé de transit dérivée (« vault:v1:… »).
"""

import base64
import os
from typing import Protocol

import httpx
import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

EMBEDDING_DTYPE = np.float32


class CipherError(RuntimeError):
    pass


class EmbeddingCipher(Protocol):
    async def encrypt(self, embedding: np.ndarray, owner_id: str) -> str: ...

    async def decrypt(self, ciphertext: str, owner_id: str) -> np.ndarray: ...


def to_bytes(embedding: np.ndarray) -> bytes:
    return np.asarray(embedding, dtype=EMBEDDING_DTYPE).tobytes()


def from_bytes(raw: bytes) -> np.ndarray:
    return np.frombuffer(raw, dtype=EMBEDDING_DTYPE).copy()


class LocalCipher:
    prefix = "local:v1:"

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("La clé AES doit faire 32 octets")
        self._aead = AESGCM(key)

    @classmethod
    def from_hex(cls, key_hex: str) -> "LocalCipher":
        """Clé de 32 octets en hexadécimal (fichier de secret ou Vault)."""
        return cls(bytes.fromhex(key_hex.strip()))

    async def encrypt(self, embedding: np.ndarray, owner_id: str) -> str:
        nonce = os.urandom(12)
        sealed = self._aead.encrypt(nonce, to_bytes(embedding), owner_id.encode())
        return self.prefix + base64.b64encode(nonce + sealed).decode()

    async def decrypt(self, ciphertext: str, owner_id: str) -> np.ndarray:
        if not ciphertext.startswith(self.prefix):
            raise CipherError("Format de texte chiffré inattendu")
        raw = base64.b64decode(ciphertext[len(self.prefix) :])
        try:
            return from_bytes(self._aead.decrypt(raw[:12], raw[12:], owner_id.encode()))
        except Exception as exc:  # InvalidTag : mauvaise clé ou mauvais titulaire
            raise CipherError("Déchiffrement impossible") from exc


class VaultTransitCipher:
    def __init__(self, client: httpx.AsyncClient, key_name: str, token: str) -> None:
        self._client = client
        self._key = key_name
        self._headers = {"X-Vault-Token": token}

    async def _call(self, action: str, payload: dict) -> dict:
        try:
            response = await self._client.post(
                f"/v1/transit/{action}/{self._key}", json=payload, headers=self._headers
            )
        except httpx.HTTPError as exc:
            raise CipherError(f"Vault injoignable : {exc.__class__.__name__}") from exc
        if response.status_code != 200:
            raise CipherError(f"Vault a refusé l'opération ({response.status_code})")
        return response.json()["data"]

    @staticmethod
    def _context(owner_id: str) -> str:
        return base64.b64encode(owner_id.encode()).decode()

    async def encrypt(self, embedding: np.ndarray, owner_id: str) -> str:
        data = await self._call(
            "encrypt",
            {
                "plaintext": base64.b64encode(to_bytes(embedding)).decode(),
                "context": self._context(owner_id),
            },
        )
        return data["ciphertext"]

    async def decrypt(self, ciphertext: str, owner_id: str) -> np.ndarray:
        data = await self._call(
            "decrypt", {"ciphertext": ciphertext, "context": self._context(owner_id)}
        )
        return from_bytes(base64.b64decode(data["plaintext"]))
