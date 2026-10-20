"""Authentificateur WebAuthn logiciel pour les tests.

Joue le rôle du téléphone : crée une paire de clés ES256, répond aux défis
d'enregistrement (attestation « none ») et de connexion, avec ou sans
vérification de l'utilisateur (le « Face ID » simulé).
"""

import hashlib
import json
import os
import struct

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import bytes_to_base64url

FLAG_USER_PRESENT = 0x01
FLAG_USER_VERIFIED = 0x04
FLAG_ATTESTED_DATA = 0x40


class SoftAuthenticator:
    def __init__(self, rp_id: str = "orbe.test", origin: str = "https://orbe.test") -> None:
        self.rp_id = rp_id
        self.origin = origin
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(16)
        self.sign_count = 0

    @property
    def id(self) -> str:
        return bytes_to_base64url(self.credential_id)

    def _cose_public_key(self) -> bytes:
        numbers = self.key.public_key().public_numbers()
        return cbor2.dumps(
            {
                1: 2,
                3: -7,
                -1: 1,
                -2: numbers.x.to_bytes(32, "big"),
                -3: numbers.y.to_bytes(32, "big"),
            }
        )

    def _client_data(self, kind: str, challenge: str, origin: str | None) -> bytes:
        return json.dumps(
            {
                "type": kind,
                "challenge": challenge,
                "origin": origin or self.origin,
                "crossOrigin": False,
            }
        ).encode()

    def _auth_data(self, flags: int, extra: bytes = b"") -> bytes:
        rp_hash = hashlib.sha256(self.rp_id.encode()).digest()
        return rp_hash + bytes([flags]) + struct.pack(">I", self.sign_count) + extra

    def register(self, options: dict, *, origin: str | None = None) -> dict:
        """Réponse à navigator.credentials.create()."""
        client_data = self._client_data("webauthn.create", options["challenge"], origin)
        attested = (
            b"\x00" * 16
            + struct.pack(">H", len(self.credential_id))
            + self.credential_id
            + self._cose_public_key()
        )
        auth_data = self._auth_data(
            FLAG_USER_PRESENT | FLAG_USER_VERIFIED | FLAG_ATTESTED_DATA, attested
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": self.id,
            "rawId": self.id,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "attestationObject": bytes_to_base64url(attestation),
                "transports": ["internal"],
            },
            "clientExtensionResults": {},
            "authenticatorAttachment": "platform",
        }

    def login(
        self,
        options: dict,
        *,
        user_verified: bool = True,
        origin: str | None = None,
        bump_counter: bool = True,
    ) -> dict:
        """Réponse à navigator.credentials.get() ; user_verified=False simule un échec Face ID."""
        if bump_counter:
            self.sign_count += 1
        flags = FLAG_USER_PRESENT | (FLAG_USER_VERIFIED if user_verified else 0)
        auth_data = self._auth_data(flags)
        client_data = self._client_data("webauthn.get", options["challenge"], origin)
        signature = self.key.sign(
            auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
        )
        return {
            "id": self.id,
            "rawId": self.id,
            "type": "public-key",
            "response": {
                "clientDataJSON": bytes_to_base64url(client_data),
                "authenticatorData": bytes_to_base64url(auth_data),
                "signature": bytes_to_base64url(signature),
                "userHandle": None,
            },
            "clientExtensionResults": {},
            "authenticatorAttachment": "platform",
        }
