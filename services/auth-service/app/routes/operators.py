"""Connexion des opérateurs au back-office : identifiant → reconnaissance faciale → mot de passe.

Ordre imposé par le sujet (poste du PC Hôte, caméra USB, LED ESP8266) :

1. `POST /operators/login/identify` : l'identifiant. Toujours une consigne de visage, même
   pour un identifiant inconnu (l'échec arrive au visage, sans révéler si le compte existe).
   Exception (démarrage) : tant qu'aucun opérateur n'a de visage, le premier passe au mot de
   passe puis enregistre son visage. Ensuite, seul un administrateur enregistre les visages,
   depuis le back-office : un mot de passe connu ne suffit jamais à poser son propre visage.
2. `POST /operators/login/face` : reconnu → LED verte clignotante, étape du mot de passe ;
   non reconnu → LED rouge fixe 30 s, identification bloquée 30 s, tout est à recommencer.
3. `POST /operators/login/password` : correct → LED verte fixe 30 s et jeton ; faux → LED rouge
   clignotante 10 fois et retour à l'identifiant.

Comptes et sessions séparés de ceux des clients, JWT d'audience `orbe-bo`. bo-api relaie ces
routes et vérifie la session avec `GET /operators/me`.
"""

import logging
import uuid
from datetime import timedelta
from typing import Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, utcnow
from app.face.decision import decide, main_face, random_direction
from app.face.service import (
    analyze_frames,
    decode_frames,
    encrypted_enrollment,
    load_operator_templates,
    operator_aad,
)
from app.logging_setup import log_event
from app.metrics import (
    ACCOUNT_LOCKS,
    FACE_ENROLLMENTS,
    LOGIN_FAILURES,
    LOGINS,
    SECOND_FACTOR,
    SESSIONS_REVOKED,
)
from app.models import Operator, OperatorFaceTemplate, OperatorSession
from app.routes.auth import (
    LIVENESS_FAILED,
    client_ip,
    rate_limit,
    register_failure,
)
from app.schemas import (
    ErrorOut,
    FaceChallenge,
    FaceEnrollRequest,
    FaceStatus,
    OperatorFaceRequest,
    OperatorIdentifyRequest,
    OperatorLoginStep,
    OperatorMe,
    OperatorPasswordRequest,
    OperatorTokenResponse,
    error,
)
from app.security import normalize_email
from app.sessions import bearer, unauthorized

router = APIRouter(prefix="/operators", tags=["Back-office"])
logger = logging.getLogger("operators")

FACE_NOT_RECOGNIZED = error(
    "face_not_recognized", "Visage non reconnu. Recommencez l'identification dans 30 secondes."
)
STEP_EXPIRED = error("login_step_expired", "Étape de connexion expirée. Recommencez.")
WRONG_PASSWORD = error(
    "invalid_credentials", "Mot de passe incorrect. Recommencez l'identification."
)


# --- Sessions ----------------------------------------------------------------------------------


async def _operator_from_token(request, credentials, db, statuses):
    if credentials is None:
        raise unauthorized()
    try:
        claims = request.app.state.operator_tokens.decode(credentials.credentials)
    except jwt.PyJWTError:
        raise unauthorized() from None
    if claims.get("typ") != "operator":
        raise unauthorized()
    session = await db.get(OperatorSession, claims.get("jti"))
    if session is None or session.operator_id != claims["sub"] or session.status not in statuses:
        raise unauthorized()
    if session.expires_at <= utcnow():
        await db.execute(
            update(OperatorSession).where(OperatorSession.id == session.id).values(status="expired")
        )
        await db.commit()
        raise unauthorized()
    operator = await db.get(Operator, session.operator_id)
    if operator is None or not operator.active:
        raise unauthorized()
    return claims, session, operator


async def current_operator(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_session),
) -> tuple[dict[str, Any], OperatorSession, Operator]:
    """Session ouverte par visage + mot de passe, active en base, compte toujours actif."""
    claims, session, operator = await _operator_from_token(request, credentials, db, ("active",))
    if "face" not in session.factors.split(","):
        raise unauthorized()
    return claims, session, operator


async def enrolling_operator(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_session),
) -> tuple[dict[str, Any], OperatorSession, Operator]:
    """Première connexion d'un opérateur sans visage : seul l'enrôlement est permis."""
    return await _operator_from_token(request, credentials, db, ("enrollment",))


async def bootstrap_open(db: AsyncSession) -> bool:
    """Démarrage : aucun opérateur n'a encore de visage enregistré."""
    return await db.scalar(select(OperatorFaceTemplate.id).limit(1)) is None


async def _pending(db: AsyncSession, session_id: str, status_: str) -> OperatorSession:
    session = await db.get(OperatorSession, session_id)
    if session is None or session.status != status_ or session.expires_at <= utcnow():
        raise unauthorized(STEP_EXPIRED)
    return session


async def _close(db: AsyncSession, session_id: str, reason: str) -> None:
    await db.execute(
        update(OperatorSession)
        .where(OperatorSession.id == session_id)
        .values(status="revoked", challenge=None, revoked_at=utcnow(), revocation_reason=reason)
    )
    await db.commit()


def _token(request: Request, operator: Operator, session: OperatorSession, enrolling: bool):
    tokens = request.app.state.operator_tokens
    ttl = request.app.state.settings.bo_enrollment_seconds if enrolling else tokens.ttl
    return OperatorTokenResponse(
        access_token=tokens.issue_operator(operator.id, operator.email, operator.role, session.id),
        expires_in=ttl,
        role=operator.role,
        face_enrollment_required=enrolling,
    )


# --- 1. Identifiant ----------------------------------------------------------------------------


@router.post(
    "/login/identify",
    response_model=OperatorLoginStep,
    summary="Connexion — 1. identifiant",
    responses={
        423: {"model": ErrorOut, "description": "Compte bloqué (en-tête Retry-After)"},
        429: {"model": ErrorOut, "description": "Identification bloquée ou trop de tentatives"},
    },
)
async def identify(
    body: OperatorIdentifyRequest, request: Request, db: AsyncSession = Depends(get_session)
) -> OperatorLoginStep:
    """Démarre la connexion et renvoie la consigne de la caméra (tourner la tête). Bloqué
    30 s après un visage non reconnu (`429 identification_locked`, en-tête Retry-After)."""
    state = request.app.state
    settings = state.settings
    ip = client_ip(request)
    rate_limit(request, ip)
    retry_after = state.led.identification_retry_after()
    if retry_after:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error(
                "identification_locked",
                f"Visage non reconnu : nouvel essai possible dans {retry_after} secondes.",
            ),
            headers={"Retry-After": str(retry_after)},
        )

    operator = (
        await db.execute(select(Operator).where(Operator.email == normalize_email(body.email)))
    ).scalar_one_or_none()
    now = utcnow()
    if operator and operator.active and operator.locked_until and operator.locked_until > now:
        LOGIN_FAILURES.labels(reason="locked").inc()
        raise HTTPException(
            status.HTTP_423_LOCKED,
            detail=error("account_locked", "Compte bloqué temporairement après trop d'échecs."),
            headers={"Retry-After": str(int((operator.locked_until - now).total_seconds()) + 1)},
        )

    usable = operator if operator and operator.active else None
    enrolling = usable is not None and await bootstrap_open(db)
    direction = None if enrolling else random_direction()
    session = OperatorSession(
        id=str(uuid.uuid4()),
        operator_id=usable.id if usable else None,  # identifiant inconnu : échec au visage
        status="pending_password" if enrolling else "pending_face",
        factors="",
        challenge=direction,
        ip_address=ip,
        opened_at=now,
        expires_at=now + timedelta(seconds=settings.bo_pending_seconds),
    )
    db.add(session)
    await db.commit()
    state.led.off()
    log_event(
        logger,
        "operator_identified",
        operator_id=usable.id if usable else None,
        known=usable is not None,
        enrolling=enrolling,
        client_ip=ip,
    )
    return OperatorLoginStep(
        session_id=session.id,
        step="password" if enrolling else "face",
        face_challenge=None
        if enrolling
        else FaceChallenge(
            direction=direction,
            frames=settings.login_frames,
            interval_ms=settings.login_interval_ms,
        ),
        face_enrollment_required=enrolling,
        expires_in=settings.bo_pending_seconds,
    )


# --- 2. Visage ---------------------------------------------------------------------------------


@router.post(
    "/login/face",
    response_model=OperatorLoginStep,
    summary="Connexion — 2. reconnaissance faciale (caméra USB)",
    responses={
        401: {"model": ErrorOut, "description": "Visage non reconnu ou étape expirée"},
        422: {"model": ErrorOut, "description": "Images invalides"},
        503: {"model": ErrorOut, "description": "Reconnaissance faciale indisponible"},
    },
)
async def login_face(
    body: OperatorFaceRequest, request: Request, db: AsyncSession = Depends(get_session)
) -> OperatorLoginStep:
    """Reconnu : LED verte clignotante jusqu'au mot de passe. Non reconnu : LED rouge fixe
    30 s, identification bloquée 30 s, la caméra peut être éteinte."""
    state = request.app.state
    settings = state.settings
    ip = client_ip(request)
    rate_limit(request, ip)
    session = await _pending(db, body.session_id, "pending_face")

    frames = decode_frames(
        body.frames, max_frames=settings.login_max_frames, max_bytes=settings.frame_max_bytes
    )
    templates = (
        await load_operator_templates(
            db, state.face_cipher, session.operator_id, state.face_engine.model_name
        )
        if session.operator_id
        else []
    )
    # Analysé même pour un identifiant inconnu : même durée de réponse, rien n'est révélé
    per_frame = await analyze_frames(state.face_engine, frames)
    decision = decide(
        [main_face(faces) for faces in per_frame],
        templates,
        direction=session.challenge,
        threshold=settings.face_threshold,
        min_matching_frames=settings.face_min_matching_frames,
        min_turn_degrees=settings.liveness_min_turn_degrees,
        left_is_positive_yaw=settings.liveness_left_is_positive_yaw,
    )
    fields = {
        "operator_id": session.operator_id,
        "best_score": decision.best_score,
        "matching_frames": decision.matching_frames,
        "head_turn": decision.head_turn,
        "direction": session.challenge,
        "client_ip": ip,
    }
    if not decision.recognized:
        await _close(db, session.id, decision.reason)
        if session.operator_id:
            await register_failure(db, session.operator_id, request, Operator)
        state.led.set("red_fixed", seconds=settings.bo_face_failure_seconds)
        state.led.lock_identification(settings.bo_face_failure_seconds)
        SECOND_FACTOR.labels(result=f"operator_{decision.reason}").inc()
        log_event(logger, "operator_face_failed", reason=decision.reason, **fields)
        raise unauthorized(
            LIVENESS_FAILED if decision.reason == "liveness_failed" else FACE_NOT_RECOGNIZED
        )

    expires = utcnow() + timedelta(seconds=settings.bo_pending_seconds)
    advanced = await db.execute(
        update(OperatorSession)
        .where(OperatorSession.id == session.id, OperatorSession.status == "pending_face")
        .values(
            status="pending_password",
            factors="face",
            challenge=None,
            face_template_id=decision.template_id,
            face_score=decision.best_score,
            expires_at=expires,
        )
    )
    await db.commit()
    if advanced.rowcount != 1:
        raise unauthorized(STEP_EXPIRED)
    state.led.set("green_blink", seconds=settings.bo_pending_seconds)
    SECOND_FACTOR.labels(result="operator_recognized").inc()
    log_event(logger, "operator_face_recognized", **fields)
    return OperatorLoginStep(
        session_id=session.id, step="password", expires_in=settings.bo_pending_seconds
    )


# --- 3. Mot de passe ---------------------------------------------------------------------------


@router.post(
    "/login/password",
    response_model=OperatorTokenResponse,
    summary="Connexion — 3. mot de passe",
    responses={401: {"model": ErrorOut, "description": "Mot de passe faux ou étape expirée"}},
)
async def login_password(
    body: OperatorPasswordRequest, request: Request, db: AsyncSession = Depends(get_session)
) -> OperatorTokenResponse:
    """Correct : LED verte fixe 30 s et jeton du back-office. Faux : LED rouge clignotante
    10 fois, la connexion recommence à l'identifiant."""
    state = request.app.state
    settings = state.settings
    ip = client_ip(request)
    rate_limit(request, ip)
    session = await _pending(db, body.session_id, "pending_password")
    operator = await db.get(Operator, session.operator_id) if session.operator_id else None

    if operator is None or not await state.passwords.verify(operator.password_hash, body.password):
        await _close(db, session.id, "wrong_password")
        if operator:
            will_lock = operator.failed_logins + 1 >= settings.lockout_threshold
            await register_failure(db, operator.id, request, Operator)
            if will_lock:
                ACCOUNT_LOCKS.inc()
                log_event(logger, "operator_locked", operator_id=operator.id, client_ip=ip)
        state.led.blink_red(settings.bo_password_failure_blinks)
        LOGIN_FAILURES.labels(reason="invalid_credentials").inc()
        log_event(
            logger,
            "operator_password_failed",
            operator_id=session.operator_id,
            client_ip=ip,
        )
        raise unauthorized(WRONG_PASSWORD)

    enrolling = "face" not in session.factors.split(",")
    now = utcnow()
    ttl = settings.bo_enrollment_seconds if enrolling else state.operator_tokens.ttl
    activated = await db.execute(
        update(OperatorSession)
        .where(OperatorSession.id == session.id, OperatorSession.status == "pending_password")
        .values(
            status="enrollment" if enrolling else "active",
            factors="pwd" if enrolling else "face,pwd",
            expires_at=now + timedelta(seconds=ttl),
        )
    )
    await db.execute(
        update(Operator)
        .where(Operator.id == operator.id)
        .values(failed_logins=0, locked_until=None, last_login_at=now)
    )
    await db.commit()
    if activated.rowcount != 1:
        raise unauthorized(STEP_EXPIRED)
    await db.refresh(session)
    if enrolling:
        log_event(logger, "operator_enrollment_started", operator_id=operator.id, client_ip=ip)
    else:
        state.led.set("green_fixed", seconds=settings.bo_success_led_seconds)
        LOGINS.inc()
        log_event(
            logger,
            "operator_login_succeeded",
            operator_id=operator.id,
            role=operator.role,
            client_ip=ip,
        )
    return _token(request, operator, session, enrolling)


# --- Première connexion : enregistrement de son visage ----------------------------------------


@router.post(
    "/me/face",
    response_model=FaceStatus,
    status_code=201,
    summary="Première connexion : enregistrer mon visage",
    responses={
        401: {"model": ErrorOut, "description": "Jeton d'enrôlement absent ou expiré"},
        422: {"model": ErrorOut, "description": "Consentement absent ou visage non détecté"},
    },
)
async def enroll_me(
    body: FaceEnrollRequest,
    request: Request,
    current: tuple[dict[str, Any], OperatorSession, Operator] = Depends(enrolling_operator),
    db: AsyncSession = Depends(get_session),
) -> FaceStatus:
    """Réservé au jeton de première connexion (`face_enrollment_required`), au démarrage
    seulement. La session est ensuite fermée : l'opérateur se reconnecte avec son visage."""
    _, session, operator = current
    if not await bootstrap_open(db):
        await _close(db, session.id, "bootstrap_closed")
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=error(
                "enrollment_by_admin",
                "Votre visage doit être enregistré par un administrateur du back-office.",
            ),
        )
    if not body.consent:
        raise HTTPException(
            422,
            detail=error("consent_required", "Le consentement explicite est requis."),
        )
    count = await store_operator_face(request, db, operator.id, body.frames)
    await _close(db, session.id, "enrollment_done")
    log_event(logger, "operator_face_enrolled", operator_id=operator.id, by="self", templates=count)
    return FaceStatus(
        enrolled=True,
        templates=count,
        model=request.app.state.face_engine.model_name,
        consent_at=utcnow().isoformat(timespec="seconds") + "Z",
    )


async def store_operator_face(
    request: Request, db: AsyncSession, operator_id: str, frames: list[str]
) -> int:
    """Remplace les gabarits de l'opérateur (aussi utilisé par l'administration)."""
    state = request.app.state
    encrypted = await encrypted_enrollment(state, frames, operator_aad(operator_id))
    now = utcnow()
    await db.execute(
        delete(OperatorFaceTemplate).where(OperatorFaceTemplate.operator_id == operator_id)
    )
    db.add_all(
        OperatorFaceTemplate(
            id=str(uuid.uuid4()),
            operator_id=operator_id,
            embedding_ct=ciphertext,
            embedding_dim=len(face.embedding),
            model=state.face_engine.model_name,
            quality_score=round(face.det_score, 3),
            captured_at=now,
        )
        for ciphertext, face in encrypted
    )
    await db.execute(
        update(Operator).where(Operator.id == operator_id).values(biometric_consent_at=now)
    )
    await db.commit()
    FACE_ENROLLMENTS.labels(result="operator_enrolled").inc()
    return len(encrypted)


# --- Session en cours --------------------------------------------------------------------------


@router.post(
    "/logout",
    status_code=204,
    summary="Déconnexion d'un opérateur (révoque la session)",
    responses={401: {"model": ErrorOut, "description": "Session invalide ou expirée"}},
)
async def logout(
    current: tuple[dict[str, Any], OperatorSession, Operator] = Depends(current_operator),
    db: AsyncSession = Depends(get_session),
) -> Response:
    _, session, operator = current
    await _close(db, session.id, "logout")
    SESSIONS_REVOKED.labels(reason="operator_logout").inc()
    log_event(logger, "operator_session_revoked", reason="logout", operator_id=operator.id)
    return Response(status_code=204)


@router.get(
    "/me",
    response_model=OperatorMe,
    summary="Opérateur connecté (sert aussi à bo-api pour vérifier la session)",
    responses={401: {"model": ErrorOut, "description": "Jeton absent, invalide ou révoqué"}},
)
async def me(
    current: tuple[dict[str, Any], OperatorSession, Operator] = Depends(current_operator),
) -> OperatorMe:
    _, session, operator = current
    return OperatorMe(
        operator_id=operator.id,
        email=operator.email,
        display_name=operator.display_name,
        role=operator.role,
        session_id=session.id,
        expires_at=session.expires_at.isoformat(timespec="seconds") + "Z",
        factors=session.factors.split(","),
    )
