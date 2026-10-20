"""Gestion des passkeys (un appareil = une passkey)."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import passkeys as webauthn
from app.db import get_session, utcnow
from app.logging_setup import log_event
from app.metrics import PASSKEY_REGISTRATIONS
from app.models import Client, Passkey, Session
from app.schemas import ErrorOut, PasskeyOut, PasskeyRegisterRequest, error
from app.sessions import current_session

router = APIRouter(prefix="/passkeys", tags=["Passkeys"])
logger = logging.getLogger("passkeys")

CONFIRMATION_REQUIRED = error(
    "passkey_confirmation_required",
    "Reconnectez-vous avec une passkey existante pour gérer vos appareils.",
)
STRONG = {
    401: {"model": ErrorOut, "description": "Session invalide ou expirée"},
    403: {"model": ErrorOut, "description": "Session sans passkey alors que le compte en a"},
}


def iso(value) -> str | None:
    return value.isoformat(timespec="seconds") + "Z" if value else None


def passkey_out(passkey: Passkey) -> PasskeyOut:
    return PasskeyOut(
        id=passkey.id,
        device_name=passkey.device_name,
        created_at=iso(passkey.created_at),
        last_used_at=iso(passkey.last_used_at),
    )


async def _registered(db: AsyncSession, client_id: str) -> list[Passkey]:
    return list(
        (await db.execute(select(Passkey).where(Passkey.client_id == client_id))).scalars().all()
    )


def _require_strong_session(session: Session, registered: list[Passkey]) -> None:
    """Un compte qui a déjà une passkey ne gère ses appareils que depuis une session
    confirmée par passkey : le mot de passe seul ne suffit pas à ajouter un appareil."""
    if registered and "passkey" not in session.factor_list:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=CONFIRMATION_REQUIRED)


@router.post(
    "/register/options", summary="Préparer l'enregistrement d'une passkey", responses=STRONG
)
async def registration_options(
    request: Request,
    current: tuple[dict[str, Any], Session] = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Options à passer à `navigator.credentials.create()`."""
    _, session = current
    client = await db.get(Client, session.client_id)
    registered = await _registered(db, client.id)
    _require_strong_session(session, registered)
    challenge = webauthn.registration_challenge(request.app.state.settings, client, registered)
    await db.execute(
        update(Session)
        .where(Session.id == session.id)
        .values(webauthn_challenge=challenge.challenge, challenge_purpose="register")
    )
    await db.commit()
    return challenge.options


@router.post(
    "/register",
    status_code=201,
    response_model=PasskeyOut,
    summary="Enregistrer la passkey de cet appareil",
    responses={
        **STRONG,
        409: {
            "model": ErrorOut,
            "description": "Aucun enregistrement en cours, ou passkey déjà connue",
        },
        422: {"model": ErrorOut, "description": "Réponse de l'appareil refusée"},
    },
)
async def register(
    body: PasskeyRegisterRequest,
    request: Request,
    current: tuple[dict[str, Any], Session] = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> PasskeyOut:
    _, session = current
    registered = await _registered(db, session.client_id)
    _require_strong_session(session, registered)
    if session.challenge_purpose != "register" or not session.webauthn_challenge:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=error(
                "no_registration_in_progress", "Demandez d'abord les options d'enregistrement."
            ),
        )
    try:
        new = webauthn.verify_registration(
            request.app.state.settings, body.credential, session.webauthn_challenge
        )
    except webauthn.PasskeyError:
        log_event(logger, "passkey_registration_failed", client_id=session.client_id)
        raise HTTPException(
            422,
            detail=error("invalid_passkey", "La réponse de l'appareil a été refusée."),
        ) from None

    consumed = await db.execute(
        update(Session)
        .where(Session.id == session.id, Session.webauthn_challenge == session.webauthn_challenge)
        .values(webauthn_challenge=None, challenge_purpose=None)
    )
    if consumed.rowcount != 1:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=error("no_registration_in_progress", "Cet enregistrement a déjà été utilisé."),
        )
    passkey = Passkey(
        id=str(uuid.uuid4()),
        client_id=session.client_id,
        credential_id=new.credential_id,
        public_key=new.public_key,
        sign_count=new.sign_count,
        device_name=body.device_name,
        created_at=utcnow(),
    )
    db.add(passkey)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=error("passkey_already_registered", "Cette passkey est déjà enregistrée."),
        ) from None
    PASSKEY_REGISTRATIONS.inc()
    log_event(logger, "passkey_registered", client_id=session.client_id, passkey_id=passkey.id)
    return passkey_out(passkey)


@router.get("", response_model=list[PasskeyOut], summary="Mes appareils", responses=STRONG)
async def list_passkeys(
    current: tuple[dict[str, Any], Session] = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> list[PasskeyOut]:
    _, session = current
    return [passkey_out(p) for p in await _registered(db, session.client_id)]


@router.delete(
    "/{passkey_id}",
    status_code=204,
    summary="Retirer un appareil",
    responses={**STRONG, 404: {"model": ErrorOut, "description": "Passkey inconnue"}},
)
async def delete_passkey(
    passkey_id: str,
    current: tuple[dict[str, Any], Session] = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> Response:
    _, session = current
    registered = await _registered(db, session.client_id)
    _require_strong_session(session, registered)
    if passkey_id not in {p.id for p in registered}:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=error("passkey_not_found", "Passkey inconnue.")
        )
    await db.execute(
        update(Session).where(Session.passkey_id == passkey_id).values(passkey_id=None)
    )
    await db.execute(delete(Passkey).where(Passkey.id == passkey_id))
    await db.commit()
    log_event(logger, "passkey_deleted", client_id=session.client_id, passkey_id=passkey_id)
    return Response(status_code=204)
