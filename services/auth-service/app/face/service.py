"""Opérations de reconnaissance faciale utilisées par les routes : images, gabarits, analyse."""

import asyncio
import base64
import binascii
import time

import numpy as np
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.face.cipher import CipherError, EmbeddingCipher
from app.face.decision import same_person, select_for_enrollment
from app.face.engine import FaceEngine, FaceObservation, FrameError
from app.metrics import FACE_ENROLLMENTS, FACE_INFERENCE_SECONDS
from app.models import ClientFaceTemplate, OperatorFaceTemplate
from app.schemas import error


def decode_frames(frames: list[str], *, max_frames: int, max_bytes: int) -> list[bytes]:
    if len(frames) > max_frames:
        raise HTTPException(422, detail=error("too_many_frames", f"{max_frames} images au plus."))
    decoded = []
    for frame in frames:
        if len(frame) > max_bytes * 4 // 3 + 4:
            raise HTTPException(422, detail=error("frame_too_large", "Image trop volumineuse."))
        try:
            decoded.append(base64.b64decode(frame, validate=True))
        except (binascii.Error, ValueError):
            raise HTTPException(422, detail=error("invalid_frame", "Image illisible.")) from None
    return decoded


async def analyze_frames(engine: FaceEngine, frames: list[bytes]) -> list[list[FaceObservation]]:
    """Visages détectés dans chaque image. Les images ne sont jamais écrites sur le disque."""
    start = time.perf_counter()
    try:
        results = await asyncio.gather(*(engine.analyze(frame) for frame in frames))
    except FrameError:
        raise HTTPException(422, detail=error("invalid_frame", "Image illisible.")) from None
    FACE_INFERENCE_SECONDS.observe(time.perf_counter() - start)
    return list(results)


UNAVAILABLE = error("face_unavailable", "Reconnaissance faciale indisponible.")


def operator_aad(operator_id: str) -> str:
    """Donnée liée au chiffrement d'un gabarit d'opérateur : distincte de celle des clients,
    un gabarit de client recopié chez un opérateur ne se déchiffre pas."""
    return f"operator:{operator_id}"


async def _load(db, cipher, column, id_column, owner_id, aad, model):
    rows = (
        await db.execute(
            select(id_column, column.table.c.embedding_ct).where(
                column == owner_id, column.table.c.model == model
            )
        )
    ).all()
    try:
        return [(row[0], await cipher.decrypt(row[1], aad)) for row in rows]
    except CipherError:
        raise HTTPException(503, detail=UNAVAILABLE) from None


async def load_templates(
    db: AsyncSession, cipher: EmbeddingCipher, client_id: str, model: str
) -> list[tuple[str, np.ndarray]]:
    """Gabarits déchiffrés du client, pour le modèle en service uniquement."""
    return await _load(
        db, cipher, ClientFaceTemplate.client_id, ClientFaceTemplate.id, client_id, client_id, model
    )


async def load_operator_templates(
    db: AsyncSession, cipher: EmbeddingCipher, operator_id: str, model: str
) -> list[tuple[str, np.ndarray]]:
    return await _load(
        db,
        cipher,
        OperatorFaceTemplate.operator_id,
        OperatorFaceTemplate.id,
        operator_id,
        operator_aad(operator_id),
        model,
    )


async def count_templates(db: AsyncSession, client_id: str) -> int:
    rows = await db.execute(
        select(ClientFaceTemplate.id).where(ClientFaceTemplate.client_id == client_id)
    )
    return len(rows.all())


async def count_operator_templates(db: AsyncSession, operator_id: str) -> int:
    rows = await db.execute(
        select(OperatorFaceTemplate.id).where(OperatorFaceTemplate.operator_id == operator_id)
    )
    return len(rows.all())


async def encrypted_enrollment(
    state, frames_b64: list[str], aad: str
) -> list[tuple[str, FaceObservation]]:
    """Images d'enrôlement → 3 à 5 gabarits chiffrés (angles variés, une seule personne).

    Commun aux clients et aux opérateurs ; lève une erreur 422 ou 503 explicite.
    """
    settings = state.settings
    frames = decode_frames(
        frames_b64, max_frames=settings.enroll_max_frames, max_bytes=settings.frame_max_bytes
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
            422, detail=error("enrollment_failed", "Les images montrent plusieurs personnes.")
        )
    try:
        return [(await state.face_cipher.encrypt(face.embedding, aad), face) for face in selected]
    except CipherError:
        raise HTTPException(503, detail=UNAVAILABLE) from None
