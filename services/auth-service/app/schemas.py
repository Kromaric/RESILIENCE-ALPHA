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


class FaceVerifyRequest(BaseModel):
    frames: list[str] = Field(min_length=1, max_length=20, description=FRAMES_DESCRIPTION)
    # Ignoré : la consigne est celle mémorisée par GET /face/challenge (gardé par compatibilité)
    direction: Literal["left", "right"] | None = None


class FaceVerifyResponse(BaseModel):
    verified: bool
    confidence: float
    token: TokenResponse


class FaceStatus(BaseModel):
    enrolled: bool
    templates: int
    model: str | None
    consent_at: str | None
    token: TokenResponse | None = None


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


# --- Back-office : connexion des opérateurs et habilitations -----------------------------------

OperatorRole = Literal["viewer", "operator", "admin"]


class OperatorIdentifyRequest(BaseModel):
    model_config = {"json_schema_extra": {"examples": [{"email": "ops@orbe.test"}]}}

    email: str = Field(min_length=3, max_length=254)


class OperatorLoginStep(BaseModel):
    """Étape suivante de la connexion au back-office."""

    session_id: str
    step: Literal["face", "password"]
    face_challenge: FaceChallenge | None = None
    face_enrollment_required: bool = (
        False  # aucun visage enregistré : mot de passe, puis enrôlement
    )
    expires_in: int


class OperatorFaceRequest(BaseModel):
    session_id: str = Field(min_length=36, max_length=36)
    frames: list[str] = Field(min_length=1, max_length=20, description=FRAMES_DESCRIPTION)


class OperatorPasswordRequest(BaseModel):
    session_id: str = Field(min_length=36, max_length=36)
    password: str = Field(min_length=1, max_length=128)


class OperatorTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — type de jeton, pas un secret
    expires_in: int
    role: OperatorRole
    # True : jeton limité à POST /operators/me/face, puis nouvelle connexion avec le visage
    face_enrollment_required: bool = False


class OperatorMe(BaseModel):
    operator_id: str
    email: str
    display_name: str
    role: OperatorRole
    session_id: str
    expires_at: str
    factors: list[str]


class OperatorAccount(BaseModel):
    operator_id: str
    email: str
    display_name: str
    role: OperatorRole
    active: bool
    locked: bool
    face_enrolled: bool
    face_templates: int
    biometric_consent_at: str | None
    last_login_at: str | None
    created_at: str
    active_sessions: int


class OperatorCreate(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "lea.soc@orbe.test",
                    "display_name": "Léa (SOC)",
                    "role": "operator",
                    "password": "un-mot-de-passe-solide",
                }
            ]
        }
    }

    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=2, max_length=80)
    role: OperatorRole = "viewer"
    password: str = Field(min_length=1, max_length=128, description="12 caractères minimum")


class OperatorUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    role: OperatorRole | None = None
    active: bool | None = None


class OperatorPasswordReset(BaseModel):
    password: str = Field(min_length=1, max_length=128, description="12 caractères minimum")
