"""Enrôlement et effacement du visage du client (RGPD : consentement et droit à l'effacement)."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, utcnow
from app.face.cipher import CipherError
from app.face.decision import decide, main_face, random_direction, same_person, select_for_enrollment
from app.face.service import analyze_frames, count_templates, decode_frames, load_templates
from app.logging_setup import log_event
from app.metrics import FACE_ENROLLMENTS, SECOND_FACTOR
from app.models import Client, ClientApi, ClientFaceTemplate, Session
from app.schemas import (
    ErrorOut,
    FaceChallenge,
    FaceEnrollRequest,
    FaceStatus,
    FaceVerifyRequest,
    FaceVerifyResponse,
    TokenResponse,
    error,
)
from app.sessions import current_session, token_for

router = APIRouter(prefix="/face", tags=["Visage"])
logger = logging.getLogger("face")

CONFIRMATION_REQUIRED = error(
    "face_confirmation_required",
    "Reconnectez-vous avec votre visage pour modifier ou supprimer votre visage enregistré.",
)
STRONG = {
    401: {"model": ErrorOut, "description": "Session invalide ou expirée"},
    403: {"model": ErrorOut, "description": "Session sans visage alors que le compte en a un"},
}


async def _status(db: AsyncSession, client: Client, model: str) -> FaceStatus:
    count = await count_templates(db, client.id)
    consent = client.biometric_consent_at
    return FaceStatus(
        enrolled=count > 0,
        templates=count,
        model=model if count else None,
        consent_at=consent.isoformat(timespec="seconds") + "Z" if consent else None,
    )


async def _require_strong_session(
    db: AsyncSession, claims: dict[str, Any], session: Session
) -> None:
    """Un compte qui a déjà un visage enregistré ne le modifie que depuis une session confirmée
    par ce visage : le mot de passe seul ne permet pas de remplacer le visage du titulaire."""
    if claims.get("cty") == "service":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=error("client_not_allowed", "Opération réservée aux clients."),
        )
    if await count_templates(db, session.client_id) and "face" not in session.factor_list:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=CONFIRMATION_REQUIRED)


@router.get("", response_model=FaceStatus, summary="Mon visage enregistré", responses=STRONG)
async def face_status(
    request: Request,
    current: tuple[dict[str, Any], Session] = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> FaceStatus:
    _, session = current
    client = await db.get(Client, session.client_id)
    return await _status(db, client, request.app.state.face_engine.model_name)


@router.get(
    "/challenge",
    response_model=FaceChallenge,
    summary="Obtenir une consigne de test du vivant pour vérification biométrique",
    responses=STRONG,
)
async def get_face_challenge(
    request: Request,
    current: tuple[dict[str, Any], Session] = Depends(current_session),
) -> FaceChallenge:
    state = request.app.state
    settings = state.settings
    return FaceChallenge(
        direction=random_direction(),
        frames=settings.login_frames,
        interval_ms=250,
    )


@router.post(
    "/verify",
    response_model=FaceVerifyResponse,
    summary="Vérifier le visage et élever la session en authentification forte (2FA)",
    responses={
        **STRONG,
        401: {
            "model": ErrorOut,
            "description": "Visage non reconnu ou test du vivant échoué",
        },
        422: {"model": ErrorOut, "description": "Images invalides ou visage non détecté"},
        503: {"model": ErrorOut, "description": "Reconnaissance faciale indisponible"},
    },
)
async def verify_face(
    body: FaceVerifyRequest,
    request: Request,
    current: tuple[dict[str, Any], Session] = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> FaceVerifyResponse:
    claims, session = current
    state = request.app.state
    settings = state.settings

    templates = await load_templates(
        db, state.face_cipher, session.client_id, state.face_engine.model_name
    )
    if not templates:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=error("no_face_enrolled", "Aucun visage enregistré pour ce compte."),
        )

    frames = decode_frames(
        body.frames, max_frames=settings.login_max_frames, max_bytes=settings.frame_max_bytes
    )
    per_frame = await analyze_frames(state.face_engine, frames)
    decision = decide(
        [main_face(faces) for faces in per_frame],
        templates,
        direction=body.direction,
        threshold=settings.face_threshold,
        min_matching_frames=settings.face_min_matching_frames,
        min_turn_degrees=settings.liveness_min_turn_degrees,
        left_is_positive_yaw=settings.liveness_left_is_positive_yaw,
    )

    if not decision.recognized:
        SECOND_FACTOR.labels(result=decision.reason).inc()
        log_event(
            logger,
            "face_verify_failed",
            client_id=session.client_id,
            reason=decision.reason,
            best_score=decision.best_score,
        )
        detail = (
            error("liveness_failed", "Mouvement de la tête non détecté dans le sens demandé.")
            if decision.reason == "liveness_failed"
            else error("second_factor_failed", "Visage non reconnu.")
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=detail)

    await db.execute(
        update(Session)
        .where(Session.id == session.id)
        .values(
            factors="pwd,face",
            face_template_id=decision.template_id,
            face_score=decision.best_score,
        )
    )
    await db.commit()
    await db.refresh(session)

    client = await db.get(Client, session.client_id)
    api = await db.get(ClientApi, session.client_api_id)
    new_token = token_for(request, client, session, api)
    SECOND_FACTOR.labels(result="recognized").inc()
    log_event(
        logger,
        "face_verify_succeeded",
        client_id=session.client_id,
        score=decision.best_score,
    )

    return FaceVerifyResponse(
        verified=True,
        confidence=round(decision.best_score * 100, 1),
        token=new_token,
    )


@router.post(
    "/enroll",
    response_model=FaceStatus,
    status_code=201,
    summary="Enregistrer (ou remplacer) mon visage",
    responses={
        **STRONG,
        422: {
            "model": ErrorOut,
            "description": "Consentement absent, visage non détecté ou plusieurs personnes",
        },
        503: {"model": ErrorOut, "description": "Reconnaissance faciale indisponible"},
    },
)
async def enroll(
    body: FaceEnrollRequest,
    request: Request,
    current: tuple[dict[str, Any], Session] = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> FaceStatus:
    """Environ 16 images en tournant lentement la tête de gauche à droite. Seuls 3 à 5
    gabarits (embeddings) sont conservés, chiffrés ; aucune image n'est stockée."""
    claims, session = current
    state = request.app.state
    settings = state.settings
    await _require_strong_session(db, claims, session)
    if not body.consent:
        raise HTTPException(
            422,
            detail=error(
                "consent_required",
                "Le consentement explicite est requis pour enregistrer votre visage.",
            ),
        )

    frames = decode_frames(
        body.frames, max_frames=settings.enroll_max_frames, max_bytes=settings.frame_max_bytes
    )
    selected = select_for_enrollment(
        await analyze_frames(state.face_engine, frames),
        count=settings.enroll_templates,
        min_quality=settings.enroll_min_quality,
    )
    if len(selected) < settings.enroll_min_templates:
        FACE_ENROLLMENTS.labels(result="not_enough_faces").inc()
        raise HTTPException(
            422,
            detail=error(
                "enrollment_failed",
                "Visage non détecté sur assez d'images : regardez la caméra, seul, bien éclairé, "
                "et tournez lentement la tête.",
            ),
        )
    if not same_person(selected, settings.face_threshold):
        FACE_ENROLLMENTS.labels(result="several_people").inc()
        raise HTTPException(
            422,
            detail=error("enrollment_failed", "Les images montrent plusieurs personnes."),
        )

    try:
        encrypted = [
            (await state.face_cipher.encrypt(face.embedding, session.client_id), face)
            for face in selected
        ]
    except CipherError:
        raise HTTPException(
            503, detail=error("face_unavailable", "Reconnaissance faciale indisponible.")
        ) from None

    now = utcnow()
    await db.execute(
        delete(ClientFaceTemplate).where(ClientFaceTemplate.client_id == session.client_id)
    )
    db.add_all(
        ClientFaceTemplate(
            id=str(uuid.uuid4()),
            client_id=session.client_id,
            embedding_ct=ciphertext,
            embedding_dim=len(face.embedding),
            model=state.face_engine.model_name,
            quality_score=round(face.det_score, 3),
            captured_at=now,
        )
        for ciphertext, face in encrypted
    )
    await db.execute(
        update(Client).where(Client.id == session.client_id).values(biometric_consent_at=now)
    )
    # Elevate session factors to strong session upon successful enrollment
    await db.execute(
        update(Session).where(Session.id == session.id).values(factors="pwd,face")
    )
    await db.commit()
    FACE_ENROLLMENTS.labels(result="enrolled").inc()
    log_event(logger, "face_enrolled", client_id=session.client_id, templates=len(encrypted))
    client = await db.get(Client, session.client_id)
    await db.refresh(client)
    await db.refresh(session)
    api = await db.get(ClientApi, session.client_api_id)

    res_status = await _status(db, client, state.face_engine.model_name)
    res_status.token = token_for(request, client, session, api)
    return res_status


@router.delete(
    "",
    status_code=204,
    summary="Supprimer mon visage (droit à l'effacement)",
    responses=STRONG,
)
async def erase(
    current: tuple[dict[str, Any], Session] = Depends(current_session),
    db: AsyncSession = Depends(get_session),
) -> Response:
    """Efface définitivement les gabarits et le consentement. La connexion repassera par
    l'enrôlement du visage."""
    claims, session = current
    await _require_strong_session(db, claims, session)
    await db.execute(
        delete(ClientFaceTemplate).where(ClientFaceTemplate.client_id == session.client_id)
    )
    await db.execute(
        update(Client).where(Client.id == session.client_id).values(biometric_consent_at=None)
    )
    await db.commit()
    log_event(logger, "face_erased", client_id=session.client_id)
    return Response(status_code=204)
