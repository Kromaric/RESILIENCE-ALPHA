"""Second facteur WebAuthn (passkeys), CADRAGE §4.2.

La biométrie (Face ID, Windows Hello) est vérifiée par l'appareil : le serveur ne voit
qu'une signature et ne conserve que la clé publique de la passkey.
"""

import json
from dataclasses import dataclass
from typing import Any

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.exceptions import WebAuthnException
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.config import Settings
from app.models import Client, Passkey

WEBAUTHN_ERRORS = (WebAuthnException, ValueError, KeyError, TypeError)


class PasskeyError(Exception):
    """Réponse de l'appareil refusée (signature, défi, origine, vérification utilisateur…)."""


@dataclass(frozen=True)
class Challenge:
    options: dict[str, Any]  # à transmettre tel quel à navigator.credentials.*
    challenge: str  # base64url, conservé dans la session


@dataclass(frozen=True)
class NewPasskey:
    credential_id: str
    public_key: str
    sign_count: int


def credential_id_of(credential: dict[str, Any]) -> str:
    raw = credential.get("rawId") or credential.get("id")
    if not isinstance(raw, str) or not raw:
        raise PasskeyError("Identifiant de passkey absent.")
    return raw


def _descriptor(passkey: Passkey) -> PublicKeyCredentialDescriptor:
    return PublicKeyCredentialDescriptor(id=base64url_to_bytes(passkey.credential_id))


def login_challenge(settings: Settings, passkeys: list[Passkey]) -> Challenge:
    options = generate_authentication_options(
        rp_id=settings.webauthn_rp_id,
        allow_credentials=[_descriptor(p) for p in passkeys],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return Challenge(json.loads(options_to_json(options)), bytes_to_base64url(options.challenge))


def verify_login(
    settings: Settings, credential: dict[str, Any], challenge: str, passkey: Passkey
) -> int:
    """Vérifie la signature de l'appareil ; retourne le nouveau compteur de signatures.

    Un compteur qui n'augmente pas signale une passkey clonée : refus.
    """
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origins,
            credential_public_key=base64url_to_bytes(passkey.public_key),
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except WEBAUTHN_ERRORS as exc:
        raise PasskeyError(str(exc)) from None
    return verified.new_sign_count


def registration_challenge(
    settings: Settings, client: Client, existing: list[Passkey]
) -> Challenge:
    options = generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=client.id.encode(),
        user_name=client.email,
        user_display_name=client.display_name,
        exclude_credentials=[_descriptor(p) for p in existing],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    return Challenge(json.loads(options_to_json(options)), bytes_to_base64url(options.challenge))


def verify_registration(
    settings: Settings, credential: dict[str, Any], challenge: str
) -> NewPasskey:
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge),
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origins,
            require_user_verification=True,
        )
    except WEBAUTHN_ERRORS as exc:
        raise PasskeyError(str(exc)) from None
    return NewPasskey(
        credential_id=bytes_to_base64url(verified.credential_id),
        public_key=bytes_to_base64url(verified.credential_public_key),
        sign_count=verified.sign_count,
    )
