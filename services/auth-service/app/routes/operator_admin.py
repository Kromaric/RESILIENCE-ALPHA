"""Gestion des habilitations du back-office : comptes opérateurs, rôles, visages, sessions.

Réservé au rôle `admin`, depuis une session ouverte par visage + mot de passe. Chaque action
est journalisée (qui, quoi, sur qui) pour le SOC. Pas de suppression de compte : un compte
est désactivé (traçabilité), ce qui révoque ses sessions. Il reste toujours au moins un
administrateur actif.

L'enregistrement du visage d'un opérateur se fait sur le poste du back-office, la personne
devant la caméra USB, avec son consentement explicite.
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session, utcnow
from app.logging_setup import log_event
from app.metrics import SESSIONS_REVOKED
from app.models import Operator, OperatorFaceTemplate, OperatorSession
from app.routes.operators import current_operator, store_operator_face
from app.schemas import (
    ErrorOut,
    FaceEnrollRequest,
    OperatorAccount,
    OperatorCreate,
    OperatorPasswordReset,
    OperatorUpdate,
    error,
)
from app.security import normalize_email, password_problem, valid_email

router = APIRouter(prefix="/operators/accounts", tags=["Back-office — habilitations"])
logger = logging.getLogger("operator_admin")

RESPONSES = {
    401: {"model": ErrorOut, "description": "Session invalide ou expirée"},
    403: {"model": ErrorOut, "description": "Réservé au rôle « admin »"},
}
NOT_FOUND = {404: {"model": ErrorOut, "description": "Opérateur inconnu"}}

# Seules ces colonnes sont insérées (droit INSERT par colonne, voir 02-users.sh)
INSERT_OPERATOR = text(
    "INSERT INTO operators (id, email, display_name, password_hash, role) "
    "VALUES (:id, :email, :display_name, :password_hash, :role)"
)


async def require_admin(
    current: tuple[dict[str, Any], OperatorSession, Operator] = Depends(current_operator),
) -> Operator:
    _, _, operator = current
    if operator.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=error("forbidden", "Gestion des habilitations réservée aux administrateurs."),
        )
    return operator


def audit(admin: Operator, action: str, target_id: str, **fields) -> None:
    log_event(
        logger,
        "operator_admin_action",
        action=action,
        admin_id=admin.id,
        target_id=target_id,
        **fields,
    )


async def _get(db: AsyncSession, operator_id: str) -> Operator:
    operator = await db.get(Operator, operator_id)
    if operator is None:
        raise HTTPException(404, detail=error("not_found", "Opérateur inconnu."))
    return operator


async def _revoke_sessions(db: AsyncSession, operator_id: str, reason: str) -> int:
    result = await db.execute(
        update(OperatorSession)
        .where(
            OperatorSession.operator_id == operator_id,
            OperatorSession.status.in_(
                ("pending_face", "pending_password", "enrollment", "active")
            ),
        )
        .values(status="revoked", revoked_at=utcnow(), revocation_reason=reason)
    )
    await db.commit()
    if result.rowcount:
        SESSIONS_REVOKED.labels(reason=reason).inc(result.rowcount)
    return result.rowcount


async def _account(db: AsyncSession, operator: Operator) -> OperatorAccount:
    now = utcnow()
    templates = await db.scalar(
        select(func.count()).where(OperatorFaceTemplate.operator_id == operator.id)
    )
    sessions = await db.scalar(
        select(func.count()).where(
            OperatorSession.operator_id == operator.id,
            OperatorSession.status == "active",
            OperatorSession.expires_at > now,
        )
    )

    def iso(value):
        return value.isoformat(timespec="seconds") + "Z" if value else None

    return OperatorAccount(
        operator_id=operator.id,
        email=operator.email,
        display_name=operator.display_name,
        role=operator.role,
        active=operator.active,
        locked=bool(operator.locked_until and operator.locked_until > now),
        face_enrolled=bool(templates),
        face_templates=templates or 0,
        biometric_consent_at=iso(operator.biometric_consent_at),
        last_login_at=iso(operator.last_login_at),
        created_at=iso(operator.created_at),
        active_sessions=sessions or 0,
    )


async def _ensure_another_admin(db: AsyncSession, operator: Operator) -> None:
    """Refuse de retirer le dernier administrateur actif (plus personne ne gérerait les accès)."""
    if operator.role != "admin" or not operator.active:
        return
    others = await db.scalar(
        select(func.count()).where(
            Operator.role == "admin", Operator.active.is_(True), Operator.id != operator.id
        )
    )
    if not others:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=error("last_admin", "Il doit rester au moins un administrateur actif."),
        )


@router.get("", response_model=list[OperatorAccount], summary="Opérateurs", responses=RESPONSES)
async def list_accounts(
    _: Operator = Depends(require_admin), db: AsyncSession = Depends(get_session)
) -> list[OperatorAccount]:
    operators = (await db.execute(select(Operator).order_by(Operator.created_at))).scalars()
    return [await _account(db, operator) for operator in operators]


@router.post(
    "",
    response_model=OperatorAccount,
    status_code=201,
    summary="Créer un opérateur",
    responses={
        **RESPONSES,
        409: {"model": ErrorOut, "description": "Email déjà utilisé"},
        422: {"model": ErrorOut, "description": "Email ou mot de passe invalide"},
    },
)
async def create_account(
    body: OperatorCreate,
    request: Request,
    admin: Operator = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> OperatorAccount:
    """Le visage s'enregistre ensuite, la personne devant la caméra (`POST …/{id}/face`)."""
    email = normalize_email(body.email)
    if not valid_email(email):
        raise HTTPException(422, detail=error("invalid_email", "Adresse email invalide."))
    problem = password_problem(body.password, email)
    if problem:
        raise HTTPException(422, detail=error("weak_password", problem))
    operator_id = str(uuid.uuid4())
    try:
        await db.execute(
            INSERT_OPERATOR,
            {
                "id": operator_id,
                "email": email,
                "display_name": " ".join(body.display_name.split()),
                "password_hash": await request.app.state.passwords.hash_async(body.password),
                "role": body.role,
            },
        )
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            409, detail=error("email_taken", "Un opérateur utilise déjà cet email.")
        ) from None
    audit(admin, "create", operator_id, role=body.role)
    return await _account(db, await _get(db, operator_id))


@router.patch(
    "/{operator_id}",
    response_model=OperatorAccount,
    summary="Modifier le nom, le rôle ou l'activation",
    responses={**RESPONSES, **NOT_FOUND, 409: {"model": ErrorOut, "description": "Dernier admin"}},
)
async def update_account(
    operator_id: str,
    body: OperatorUpdate,
    admin: Operator = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> OperatorAccount:
    """Désactiver un compte révoque ses sessions ; un changement de rôle s'applique dès la
    requête suivante (bo-api relit le rôle auprès d'auth-service)."""
    operator = await _get(db, operator_id)
    changes = body.model_dump(exclude_none=True)
    if "display_name" in changes:
        changes["display_name"] = " ".join(changes["display_name"].split())
    if changes.get("role", "admin") != "admin" or changes.get("active", True) is False:
        await _ensure_another_admin(db, operator)
    if changes:
        await db.execute(update(Operator).where(Operator.id == operator.id).values(**changes))
        await db.commit()
        await db.refresh(operator)
    if changes.get("active") is False:
        await _revoke_sessions(db, operator.id, "operator_disabled")
    audit(admin, "update", operator.id, changes=sorted(changes))
    return await _account(db, operator)


@router.post(
    "/{operator_id}/password",
    status_code=204,
    summary="Définir un nouveau mot de passe",
    responses={**RESPONSES, **NOT_FOUND, 422: {"model": ErrorOut, "description": "Trop faible"}},
)
async def reset_password(
    operator_id: str,
    body: OperatorPasswordReset,
    request: Request,
    admin: Operator = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> Response:
    """Révoque les sessions de l'opérateur et lève un éventuel blocage."""
    operator = await _get(db, operator_id)
    problem = password_problem(body.password, operator.email)
    if problem:
        raise HTTPException(422, detail=error("weak_password", problem))
    await db.execute(
        update(Operator)
        .where(Operator.id == operator.id)
        .values(
            password_hash=await request.app.state.passwords.hash_async(body.password),
            failed_logins=0,
            locked_until=None,
        )
    )
    await db.commit()
    await _revoke_sessions(db, operator.id, "password_reset")
    audit(admin, "password_reset", operator.id)
    return Response(status_code=204)


@router.post(
    "/{operator_id}/unlock",
    response_model=OperatorAccount,
    summary="Débloquer un compte (après 5 échecs)",
    responses={**RESPONSES, **NOT_FOUND},
)
async def unlock(
    operator_id: str,
    admin: Operator = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> OperatorAccount:
    operator = await _get(db, operator_id)
    await db.execute(
        update(Operator)
        .where(Operator.id == operator.id)
        .values(failed_logins=0, locked_until=None)
    )
    await db.commit()
    await db.refresh(operator)
    audit(admin, "unlock", operator.id)
    return await _account(db, operator)


@router.delete(
    "/{operator_id}/sessions",
    status_code=204,
    summary="Révoquer toutes les sessions d'un opérateur",
    responses={**RESPONSES, **NOT_FOUND},
)
async def revoke_sessions(
    operator_id: str,
    admin: Operator = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> Response:
    operator = await _get(db, operator_id)
    count = await _revoke_sessions(db, operator.id, "revoked_by_admin")
    audit(admin, "revoke_sessions", operator.id, sessions=count)
    return Response(status_code=204)


@router.post(
    "/{operator_id}/face",
    response_model=OperatorAccount,
    status_code=201,
    summary="Enregistrer (ou remplacer) le visage d'un opérateur",
    responses={
        **RESPONSES,
        **NOT_FOUND,
        422: {"model": ErrorOut, "description": "Consentement absent ou visage non détecté"},
    },
)
async def enroll_face(
    operator_id: str,
    body: FaceEnrollRequest,
    request: Request,
    admin: Operator = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> OperatorAccount:
    """L'opérateur est devant la caméra USB du poste et a donné son consentement explicite
    (case à cocher). ~16 images, tête qui balaie lentement de gauche à droite."""
    operator = await _get(db, operator_id)
    if not body.consent:
        raise HTTPException(
            422,
            detail=error(
                "consent_required", "Le consentement explicite de l'opérateur est requis."
            ),
        )
    count = await store_operator_face(request, db, operator.id, body.frames)
    audit(admin, "face_enrolled", operator.id, templates=count)
    await db.refresh(operator)
    return await _account(db, operator)


@router.delete(
    "/{operator_id}/face",
    response_model=OperatorAccount,
    summary="Effacer le visage d'un opérateur (droit à l'effacement)",
    responses={**RESPONSES, **NOT_FOUND},
)
async def erase_face(
    operator_id: str,
    admin: Operator = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
) -> OperatorAccount:
    """Sans visage, l'opérateur ne peut plus se connecter : ses sessions sont révoquées."""
    operator = await _get(db, operator_id)
    await db.execute(
        delete(OperatorFaceTemplate).where(OperatorFaceTemplate.operator_id == operator.id)
    )
    await db.execute(
        update(Operator).where(Operator.id == operator.id).values(biometric_consent_at=None)
    )
    await db.commit()
    await _revoke_sessions(db, operator.id, "face_erased")
    audit(admin, "face_erased", operator.id)
    await db.refresh(operator)
    return await _account(db, operator)
