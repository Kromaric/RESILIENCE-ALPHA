"""Gestion des habilitations (rôle admin) : relais vers auth-service (`/operators/accounts`).

bo-api vérifie le rôle avant de relayer ; auth-service le revérifie (session ouverte par
visage + mot de passe) et journalise chaque action.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Path, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from app.errors import ErrorOut
from app.routes.auth import EnrollRequest, relay
from app.security import Operator, bearer, require_role

router = APIRouter(prefix="/bo/admin/operators", tags=["Habilitations"])

Role = Literal["viewer", "operator", "admin"]
OperatorId = Path(pattern=r"^[0-9a-f-]{36}$")
RESPONSES = {
    401: {"model": ErrorOut, "description": "Jeton absent, invalide ou révoqué"},
    403: {"model": ErrorOut, "description": "Réservé au rôle « admin »"},
    404: {"model": ErrorOut, "description": "Opérateur inconnu"},
}


class Account(BaseModel):
    operator_id: str
    email: str
    display_name: str
    role: Role
    active: bool
    locked: bool
    face_enrolled: bool
    face_templates: int
    biometric_consent_at: str | None
    last_login_at: str | None
    created_at: str
    active_sessions: int


class AccountCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=2, max_length=80)
    role: Role = "viewer"
    password: str = Field(min_length=1, max_length=128, description="12 caractères minimum")


class AccountUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    role: Role | None = None
    active: bool | None = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=1, max_length=128)


def token(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    return credentials.credentials


Admin = Depends(require_role("admin"))


@router.get("", response_model=list[Account], summary="Opérateurs", responses=RESPONSES)
async def list_operators(
    request: Request, _: Operator = Admin, jwt: str = Depends(token)
) -> Response:
    return await relay(request, "GET", "/operators/accounts", token=jwt)


@router.post("", response_model=Account, status_code=201, summary="Créer", responses=RESPONSES)
async def create_operator(
    body: AccountCreate, request: Request, _: Operator = Admin, jwt: str = Depends(token)
) -> Response:
    return await relay(request, "POST", "/operators/accounts", body=body, token=jwt)


@router.patch(
    "/{operator_id}", response_model=Account, summary="Nom, rôle, activation", responses=RESPONSES
)
async def update_operator(
    body: AccountUpdate,
    request: Request,
    operator_id: str = OperatorId,
    _: Operator = Admin,
    jwt: str = Depends(token),
) -> Response:
    return await relay(request, "PATCH", f"/operators/accounts/{operator_id}", body=body, token=jwt)


@router.post(
    "/{operator_id}/password", status_code=204, summary="Nouveau mot de passe", responses=RESPONSES
)
async def reset_password(
    body: PasswordReset,
    request: Request,
    operator_id: str = OperatorId,
    _: Operator = Admin,
    jwt: str = Depends(token),
) -> Response:
    return await relay(
        request, "POST", f"/operators/accounts/{operator_id}/password", body=body, token=jwt
    )


@router.post(
    "/{operator_id}/unlock", response_model=Account, summary="Débloquer", responses=RESPONSES
)
async def unlock(
    request: Request, operator_id: str = OperatorId, _: Operator = Admin, jwt: str = Depends(token)
) -> Response:
    return await relay(request, "POST", f"/operators/accounts/{operator_id}/unlock", token=jwt)


@router.delete(
    "/{operator_id}/sessions", status_code=204, summary="Révoquer ses sessions", responses=RESPONSES
)
async def revoke_sessions(
    request: Request, operator_id: str = OperatorId, _: Operator = Admin, jwt: str = Depends(token)
) -> Response:
    return await relay(request, "DELETE", f"/operators/accounts/{operator_id}/sessions", token=jwt)


@router.post(
    "/{operator_id}/face",
    response_model=Account,
    status_code=201,
    summary="Enregistrer le visage (opérateur devant la caméra, consentement)",
    responses=RESPONSES,
)
async def enroll_face(
    body: EnrollRequest,
    request: Request,
    operator_id: str = OperatorId,
    _: Operator = Admin,
    jwt: str = Depends(token),
) -> Response:
    """~16 images pendant que l'opérateur tourne lentement la tête de gauche à droite."""
    return await relay(
        request, "POST", f"/operators/accounts/{operator_id}/face", body=body, token=jwt
    )


@router.delete(
    "/{operator_id}/face", response_model=Account, summary="Effacer le visage", responses=RESPONSES
)
async def erase_face(
    request: Request, operator_id: str = OperatorId, _: Operator = Admin, jwt: str = Depends(token)
) -> Response:
    return await relay(request, "DELETE", f"/operators/accounts/{operator_id}/face", token=jwt)
