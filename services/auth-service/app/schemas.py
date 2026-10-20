from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(examples=["invalid_credentials"])
    message: str = Field(examples=["Email ou mot de passe incorrect."])


class ErrorOut(BaseModel):
    detail: ErrorDetail


class LoginRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [{"email": "client@boutique-demo.test", "password": "demo-password"}]
        }
    }

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "nathan@orbe.test",
                    "phone": "06 12 34 56 75",
                    "display_name": "Nathan Moreau",
                    "password": "correct-cheval-batterie",
                }
            ]
        }
    }

    email: str = Field(min_length=3, max_length=254)
    phone: str = Field(min_length=8, max_length=24, description="Format français ou international")
    display_name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=1, max_length=128, description="12 caractères minimum")


class RegisterResponse(BaseModel):
    client_id: str
    email: str
    phone_masked: str
    display_name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — type de jeton, pas un secret
    expires_in: int
    factors: list[str]


class LoginResponse(BaseModel):
    """Étape 1 de la connexion.

    - `mfa_required = true` : valider la passkey avec `webauthn_options`, puis
      `POST /login/passkey` ;
    - sinon : `token` est fourni. `passkey_enrollment_required = true` signale un compte
      sans passkey : la session ne permet que de consulter et d'enregistrer une passkey.
    """

    mfa_required: bool
    session_id: str
    webauthn_options: dict[str, Any] | None = None
    token: TokenResponse | None = None
    passkey_enrollment_required: bool = False


class PasskeyLoginRequest(BaseModel):
    session_id: str = Field(min_length=36, max_length=36)
    credential: dict[str, Any] = Field(description="Réponse de navigator.credentials.get()")


class PasskeyRegisterRequest(BaseModel):
    credential: dict[str, Any] = Field(description="Réponse de navigator.credentials.create()")
    device_name: str = Field(default="Mon appareil", min_length=1, max_length=80)


class PasskeyOut(BaseModel):
    id: str
    device_name: str
    created_at: str
    last_used_at: str | None


class MeResponse(BaseModel):
    client_id: str
    email: str
    phone_masked: str
    display_name: str
    factors: list[str]
    passkey_count: int


class VerifyResponse(BaseModel):
    partner: str
    scopes: list[str]


def error(code: str, message: str) -> dict[str, str]:
    """Corps d'erreur commun : {"detail": {"code", "message"}} — le front s'appuie sur code."""
    return {"code": code, "message": message}
