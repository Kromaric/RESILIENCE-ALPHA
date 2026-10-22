"""Connexion des opérateurs : relais vers auth-service, seul détenteur des comptes.

Ordre imposé par le sujet : identifiant → reconnaissance faciale (caméra USB du PC Hôte) →
mot de passe. auth-service pilote aussi la LED de l'ESP8266 à chaque étape. Le front du
dashboard ne parle qu'à bo-api ; auth-service n'a pas à être joignable depuis le navigateur.
"""

import logging
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from app.errors import ErrorOut, upstream_unavailable
from app.logging_setup import log_event
from app.metrics import OPERATOR_LOGINS, UPSTREAM_ERRORS
from app.security import Operator, bearer, current_operator

router = APIRouter(prefix="/bo/auth", tags=["Connexion"])
logger = logging.getLogger("auth")

Role = Literal["viewer", "operator", "admin"]
FRAMES = "Images JPEG en base64 de la caméra USB, prises pendant la rotation de la tête"


class IdentifyRequest(BaseModel):
    model_config = {"json_schema_extra": {"examples": [{"email": "ops@orbe.test"}]}}

    email: str = Field(min_length=3, max_length=254)


class FaceChallenge(BaseModel):
    direction: Literal["left", "right"]
    frames: int
    interval_ms: int


class LoginStep(BaseModel):
    session_id: str
    step: Literal["face", "password"]
    face_challenge: FaceChallenge | None = None
    face_enrollment_required: bool = False
    expires_in: int


class FaceRequest(BaseModel):
    session_id: str = Field(min_length=36, max_length=36)
    frames: list[str] = Field(min_length=1, max_length=20, description=FRAMES)


class PasswordRequest(BaseModel):
    session_id: str = Field(min_length=36, max_length=36)
    password: str = Field(min_length=1, max_length=128)


class EnrollRequest(BaseModel):
    consent: bool = Field(description="Consentement explicite (RGPD art. 9)")
    frames: list[str] = Field(min_length=1, max_length=30, description=FRAMES)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — type de jeton, pas un secret
    expires_in: int
    role: Role
    face_enrollment_required: bool = False


class MeResponse(BaseModel):
    operator_id: str
    email: str
    display_name: str
    role: Role


def client_ip(request: Request) -> str:
    """IP de l'opérateur transmise par le Nginx du dashboard."""
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "-")


async def relay(
    request: Request,
    method: str,
    path: str,
    *,
    body: BaseModel | None = None,
    token: str | None = None,
) -> Response:
    """Transmet la requête à auth-service et renvoie sa réponse telle quelle (codes, erreurs,
    Retry-After). auth-service injoignable ou en panne : 503 auth_unavailable."""
    state = request.app.state
    headers = {"X-Real-IP": client_ip(request)}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        upstream = await state.http.request(
            method,
            f"{state.settings.auth_url}{path}",
            json=body.model_dump(exclude_none=True) if body else None,
            headers=headers,
            timeout=state.settings.face_timeout_seconds,
        )
    except httpx.HTTPError:
        UPSTREAM_ERRORS.labels(upstream="auth").inc()
        raise upstream_unavailable("auth") from None
    if upstream.status_code in (500, 502, 504):
        UPSTREAM_ERRORS.labels(upstream="auth").inc()
        raise upstream_unavailable("auth")
    if upstream.status_code == 204:
        return Response(status_code=204)
    retry_after = upstream.headers.get("retry-after")
    return JSONResponse(
        upstream.json(),
        status_code=upstream.status_code,
        headers={"Retry-After": retry_after} if retry_after else {},
    )


STEP_ERRORS = {
    401: {"model": ErrorOut, "description": "Étape échouée ou expirée : recommencer l'identifiant"},
    429: {"model": ErrorOut, "description": "Identification bloquée 30 s (en-tête Retry-After)"},
    503: {"model": ErrorOut, "description": "auth-service ou reconnaissance faciale indisponible"},
}


@router.post(
    "/identify",
    response_model=LoginStep,
    summary="Connexion — 1. identifiant",
    responses={**STEP_ERRORS, 423: {"model": ErrorOut, "description": "Compte bloqué"}},
)
async def identify(body: IdentifyRequest, request: Request) -> Response:
    """Renvoie la consigne de la caméra (`face_challenge`) : allumer la caméra USB, puis
    `POST /bo/auth/face`. `429 identification_locked` : attendre `Retry-After` secondes
    (visage non reconnu juste avant, LED rouge fixe)."""
    return await relay(request, "POST", "/operators/login/identify", body=body)


@router.post(
    "/face",
    response_model=LoginStep,
    summary="Connexion — 2. reconnaissance faciale",
    responses=STEP_ERRORS,
)
async def face(body: FaceRequest, request: Request) -> Response:
    """`frames` : `face_challenge.frames` images toutes les `interval_ms`. Reconnu : étape
    `password` (LED verte clignotante). Non reconnu : `401`, éteindre la caméra, vider
    l'identifiant ; nouvel essai après 30 s (LED rouge fixe)."""
    return await relay(request, "POST", "/operators/login/face", body=body)


@router.post(
    "/password",
    response_model=TokenResponse,
    summary="Connexion — 3. mot de passe",
    responses=STEP_ERRORS,
)
async def password(body: PasswordRequest, request: Request) -> Response:
    """Correct : jeton (1 h), LED verte fixe 30 s, le back-office est disponible. Faux :
    `401`, LED rouge clignotante 10 fois, tout recommence à l'identifiant."""
    response = await relay(request, "POST", "/operators/login/password", body=body)
    OPERATOR_LOGINS.labels(result="success" if response.status_code == 200 else "failure").inc()
    return response


@router.post(
    "/enroll-face",
    status_code=201,
    summary="Démarrage : le premier administrateur enregistre son visage",
    responses={401: {"model": ErrorOut, "description": "Jeton d'enrôlement absent ou expiré"}},
)
async def enroll_face(
    body: EnrollRequest,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Response:
    """Seulement avec le jeton reçu quand `face_enrollment_required` vaut `true` (aucun
    opérateur n'a encore de visage). Ensuite, se reconnecter avec le visage."""
    token = credentials.credentials if credentials else None
    return await relay(request, "POST", "/operators/me/face", body=body, token=token)


@router.post(
    "/logout",
    status_code=204,
    summary="Se déconnecter (révoque la session)",
    responses={401: {"model": ErrorOut, "description": "Session invalide ou expirée"}},
)
async def logout(
    request: Request,
    operator: Operator = Depends(current_operator),
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> Response:
    await relay(request, "POST", "/operators/logout", token=credentials.credentials)
    request.app.state.operator_sessions.forget(operator.session_id)
    log_event(logger, "operator_logout", operator_id=operator.operator_id)
    return Response(status_code=204)


@router.get(
    "/me",
    response_model=MeResponse,
    summary="Opérateur connecté",
    responses={401: {"model": ErrorOut, "description": "Jeton absent, invalide ou révoqué"}},
)
async def me(operator: Operator = Depends(current_operator)) -> MeResponse:
    return MeResponse(
        operator_id=operator.operator_id,
        email=operator.email,
        display_name=operator.display_name,
        role=operator.role,
    )
