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


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — type de jeton, pas un secret
    expires_in: int


class MeResponse(BaseModel):
    client_id: str
    email: str
    phone_masked: str
    display_name: str


class VerifyResponse(BaseModel):
    partner: str
    scopes: list[str]


def error(code: str, message: str) -> dict[str, str]:
    """Corps d'erreur commun : {"detail": {"code", "message"}} — le front s'appuie sur code."""
    return {"code": code, "message": message}
