"""Connexion des opérateurs : relais vers auth-service, seul détenteur des comptes.

Le front du dashboard ne parle qu'à bo-api ; auth-service n'a pas à être joignable depuis
le navigateur de l'opérateur.
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


class LoginRequest(BaseModel):
    model_config = {
        "json_schema_extra": {"examples": [{"email": "ops@orbe.test", "password": "demo-password"}]}
    }

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — type de jeton, pas un secret
    expires_in: int
    role: Literal["viewer", "operator"]


class MeResponse(BaseModel):
    operator_id: str
    email: str
    display_name: str
    role: Literal["viewer", "operator"]


def client_ip(request: Request) -> str:
    """IP de l'opérateur transmise par le Nginx du dashboard."""
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "-")


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Se connecter (opérateur)",
    responses={
        401: {"model": ErrorOut, "description": "Identifiants invalides"},
        423: {"model": ErrorOut, "description": "Compte bloqué (en-tête Retry-After)"},
        429: {"model": ErrorOut, "description": "Trop de tentatives (en-tête Retry-After)"},
        503: {"model": ErrorOut, "description": "auth-service injoignable"},
    },
)
async def login(body: LoginRequest, request: Request) -> JSONResponse:
    """Mot de passe seul. Jeton valable 1 h, à envoyer ensuite en `Authorization: Bearer`.
    Après 5 échecs, le compte est bloqué 10 minutes."""
    state = request.app.state
    try:
        upstream = await state.http.post(
            f"{state.settings.auth_url}/operators/login",
            json=body.model_dump(),
            headers={"X-Real-IP": client_ip(request)},
        )
    except httpx.HTTPError:
        UPSTREAM_ERRORS.labels(upstream="auth").inc()
        raise upstream_unavailable("auth") from None
    if upstream.status_code >= 500:
        UPSTREAM_ERRORS.labels(upstream="auth").inc()
        raise upstream_unavailable("auth")

    OPERATOR_LOGINS.labels(result="success" if upstream.status_code == 200 else "failure").inc()
    headers = (
        {"Retry-After": upstream.headers["retry-after"]}
        if "retry-after" in upstream.headers
        else {}
    )
    return JSONResponse(upstream.json(), status_code=upstream.status_code, headers=headers)


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
    state = request.app.state
    try:
        await state.http.post(
            f"{state.settings.auth_url}/operators/logout",
            headers={"Authorization": f"Bearer {credentials.credentials}"},
        )
    except httpx.HTTPError:
        UPSTREAM_ERRORS.labels(upstream="auth").inc()
        raise upstream_unavailable("auth") from None
    state.operator_sessions.forget(operator.session_id)
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
