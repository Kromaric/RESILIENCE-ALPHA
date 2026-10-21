from typing import Literal

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
    password: str = Field(min_length=1, max_length=128, description="8 caractères minimum")


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


class FaceChallenge(BaseModel):
    """Consigne du test du vivant : filmer le visage pendant que la tête tourne dans ce sens."""

    direction: Literal["left", "right"]
    frames: int = Field(description="Nombre d'images à envoyer")
    interval_ms: int = Field(default=250, description="Intervalle conseillé entre deux images")


class LoginResponse(BaseModel):
    """Étape 1 de la connexion.

    - `mfa_required = true` : filmer le visage selon `face_challenge`, puis `POST /login/face` ;
    - sinon : `token` est fourni. `face_enrollment_required = true` signale un compte sans
      visage enregistré : la session ne permet que de consulter et d'enrôler son visage.
    """

    mfa_required: bool
    session_id: str
    face_challenge: FaceChallenge | None = None
    token: TokenResponse | None = None
    face_enrollment_required: bool = False


FRAMES_DESCRIPTION = "Images JPEG encodées en base64, capturées par la caméra du navigateur"


class FaceLoginRequest(BaseModel):
    session_id: str = Field(min_length=36, max_length=36)
    frames: list[str] = Field(min_length=1, max_length=20, description=FRAMES_DESCRIPTION)


class FaceEnrollRequest(BaseModel):
    consent: bool = Field(
        description="Consentement explicite au traitement des données biométriques (RGPD art. 9)"
    )
    frames: list[str] = Field(min_length=1, max_length=30, description=FRAMES_DESCRIPTION)


class FaceStatus(BaseModel):
    enrolled: bool
    templates: int
    model: str | None
    consent_at: str | None


class MeResponse(BaseModel):
    client_id: str
    email: str
    phone_masked: str
    display_name: str
    factors: list[str]
    face_enrolled: bool


class VerifyResponse(BaseModel):
    partner: str
    scopes: list[str]


def error(code: str, message: str) -> dict[str, str]:
    """Corps d'erreur commun : {"detail": {"code", "message"}} — le front s'appuie sur code."""
    return {"code": code, "message": message}
