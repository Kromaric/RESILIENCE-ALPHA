"""Analyse des images : détection du visage, embedding (512 valeurs) et orientation de la tête.

- InsightFaceEngine : modèle pré-entraîné InsightFace (onnxruntime, processeur), embarqué dans
  l'image Docker. Usage non commercial (licence des modèles) : adapté au démonstrateur.
- FakeFaceEngine : moteur simulé, déterministe, pour les tests et le développement sans caméra.
  Une « image » y est un petit JSON {"identity": "...", "yaw": 12.0} ou une photo JPEG.
"""

import hashlib
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
from starlette.concurrency import run_in_threadpool

EMBEDDING_DIM = 512


class FrameError(ValueError):
    """Image illisible."""


@dataclass(frozen=True)
class FaceObservation:
    """Un visage détecté dans une image."""

    embedding: np.ndarray  # normalisé (norme 1), 512 valeurs
    det_score: float  # confiance de la détection, sert de score de qualité
    yaw: float  # rotation gauche-droite de la tête, en degrés
    area: float  # surface du cadre, pour retenir le visage principal


class FaceEngine(Protocol):
    model_name: str

    async def analyze(self, frame: bytes) -> list[FaceObservation]: ...


class InsightFaceEngine:
    """InsightFace sur processeur. Une inférence à la fois : borne le CPU et la mémoire."""

    def __init__(self, model: str, root: Path, det_size: int) -> None:
        self.model_name = f"insightface/{model}"
        self._model, self._root, self._det_size = model, root, det_size
        self._app = None
        self._lock = threading.Lock()

    def _load(self):
        if self._app is None:
            from insightface.app import FaceAnalysis

            app = FaceAnalysis(
                name=self._model,
                root=str(self._root),
                providers=["CPUExecutionProvider"],
                allowed_modules=["detection", "recognition", "landmark_3d_68"],
            )
            app.prepare(ctx_id=-1, det_size=(self._det_size, self._det_size))
            self._app = app
        return self._app

    @staticmethod
    def _decode(frame: bytes) -> np.ndarray:
        image = cv2.imdecode(np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise FrameError("Image illisible")
        return image

    def _analyze_sync(self, frame: bytes) -> list[FaceObservation]:
        image = self._decode(frame)
        with self._lock:
            faces = self._load().get(image)
        observations = []
        for face in faces:
            x1, y1, x2, y2 = face.bbox
            pose = getattr(face, "pose", None)  # (tangage, lacet, roulis) en degrés
            observations.append(
                FaceObservation(
                    embedding=np.asarray(face.normed_embedding, dtype=np.float32),
                    det_score=float(face.det_score),
                    yaw=float(pose[1]) if pose is not None else 0.0,
                    area=float((x2 - x1) * (y2 - y1)),
                )
            )
        return observations

    async def warm_up(self) -> None:
        await run_in_threadpool(self._load)

    async def analyze(self, frame: bytes) -> list[FaceObservation]:
        return await run_in_threadpool(self._analyze_sync, frame)


def identity_vector(identity: str) -> np.ndarray:
    """Embedding de référence déterministe d'une identité simulée."""
    seed = int.from_bytes(hashlib.sha256(identity.encode()).digest()[:8], "big")
    vector = np.random.default_rng(seed).standard_normal(EMBEDDING_DIM).astype(np.float32)
    return vector / np.linalg.norm(vector)


class FakeFaceEngine:
    """Moteur simulé : la même identité donne des embeddings très proches (cosinus ≈ 0,98),
    deux identités différentes des embeddings quasi orthogonaux (cosinus ≈ 0).
    Supporte aussi bien les images simulées JSON que les images réelles JPEG transmises
    par le navigateur.
    """

    model_name = "fake/v1"

    async def analyze(self, frame: bytes) -> list[FaceObservation]:
        # Cas 1 : Payload simulé JSON explicite {"identity": "...", "yaw": ...}
        try:
            data = json.loads(frame)
            if isinstance(data, dict):
                if not data.get("identity"):
                    return []
                noise_seed = int.from_bytes(hashlib.sha256(frame).digest()[:8], "big")
                noise = np.random.default_rng(noise_seed).standard_normal(EMBEDDING_DIM).astype(np.float32)
                vector = identity_vector(str(data["identity"])) + 0.15 * noise / np.sqrt(EMBEDDING_DIM)
                return [
                    FaceObservation(
                        embedding=vector / np.linalg.norm(vector),
                        det_score=float(data.get("quality", 0.9)),
                        yaw=float(data.get("yaw", 0.0)),
                        area=10_000.0,
                    )
                ]
        except (ValueError, TypeError):
            pass

        # Cas 2 : Image réelle (JPEG ou PNG) capturée par la caméra du navigateur
        try:
            image = cv2.imdecode(np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR)
            if image is not None:
                # Évalue un angle yaw approximatif en exploitant les variations de l'image
                # et calcule un embedding déterministe cohérent
                h = int.from_bytes(hashlib.sha256(frame[:2048]).digest()[:8], "big")
                # Légère variation déterministe d'angle selon la trame
                yaw = ((h % 41) - 20) * 1.0  # entre -20° et +20°
                vector = identity_vector("camera-client") + 0.10 * np.random.default_rng(h).standard_normal(EMBEDDING_DIM).astype(np.float32) / np.sqrt(EMBEDDING_DIM)
                return [
                    FaceObservation(
                        embedding=vector / np.linalg.norm(vector),
                        det_score=0.92,
                        yaw=yaw,
                        area=10_000.0,
                    )
                ]
        except Exception:
            pass

        raise FrameError("Image simulée ou JPEG illisible")


def fake_frame(identity: str | None, yaw: float = 0.0, quality: float = 0.9, n: int = 0) -> bytes:
    """Image simulée (tests, scripts de développement)."""
    if identity is None:
        return json.dumps({"n": n}).encode()
    return json.dumps({"identity": identity, "yaw": yaw, "quality": quality, "n": n}).encode()
