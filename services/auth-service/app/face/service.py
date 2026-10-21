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
from app.face.engine import FaceEngine, FaceObservation, FrameError
from app.metrics import FACE_INFERENCE_SECONDS
from app.models import ClientFaceTemplate
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


async def load_templates(
    db: AsyncSession, cipher: EmbeddingCipher, client_id: str, model: str
) -> list[tuple[str, np.ndarray]]:
    """Gabarits déchiffrés du client, pour le modèle en service uniquement."""
    rows = (
        await db.execute(
            select(ClientFaceTemplate.id, ClientFaceTemplate.embedding_ct).where(
                ClientFaceTemplate.client_id == client_id, ClientFaceTemplate.model == model
            )
        )
    ).all()
    try:
        return [(row.id, await cipher.decrypt(row.embedding_ct, client_id)) for row in rows]
    except CipherError:
        raise HTTPException(
            503, detail=error("face_unavailable", "Reconnaissance faciale indisponible.")
        ) from None


async def count_templates(db: AsyncSession, client_id: str) -> int:
    rows = await db.execute(
        select(ClientFaceTemplate.id).where(ClientFaceTemplate.client_id == client_id)
    )
    return len(rows.all())
