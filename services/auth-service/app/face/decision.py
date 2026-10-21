"""Décision de reconnaissance (fonctions pures, testées sans modèle ni caméra).

Vérification 1:1 : le visage capturé est comparé aux seuls gabarits du client qui se connecte.

Test du vivant : l'utilisateur doit tourner la tête dans un sens **tiré au hasard** par le
serveur (« tournez la tête vers la gauche »). Une photo ne tourne pas, et une vidéo préenregistrée
n'a qu'une chance sur deux d'aller dans le bon sens. Ce test reste limité (pas de détection de
profondeur) : limite documentée dans le dossier.
"""

import secrets
from collections import Counter
from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.face.engine import FaceObservation

Direction = Literal["left", "right"]


def random_direction() -> Direction:
    return secrets.choice(("left", "right"))


def main_face(observations: list[FaceObservation]) -> FaceObservation | None:
    """Visage principal (le plus grand) d'une image, ou None s'il n'y en a pas."""
    return max(observations, key=lambda o: o.area) if observations else None


def head_turn(yaws: list[float], expected_sign: int = 1) -> tuple[float, float]:
    """Rotation de la tête par rapport à la position de départ (moyenne des 2 premières images).

    Renvoie (amplitude dans le sens demandé, amplitude dans le sens opposé), en degrés. Chaque
    amplitude est la 2ᵉ plus grande de la séquence : un pic isolé (bruit de mesure) ne suffit
    pas. Tourner puis revenir face à la caméra est accepté : seule l'amplitude atteinte compte.
    """
    if len(yaws) < 3:
        return 0.0, 0.0
    baseline = float(np.mean(yaws[:2]))
    excursions = sorted(expected_sign * (yaw - baseline) for yaw in yaws[2:])
    wanted = max(0.0, excursions[-2] if len(excursions) >= 2 else excursions[-1])
    opposite = max(0.0, -(excursions[1] if len(excursions) >= 2 else excursions[0]))
    return float(wanted), float(opposite)


@dataclass(frozen=True)
class Decision:
    recognized: bool
    reason: str | None  # liveness_failed | face_not_recognized
    best_score: float | None
    template_id: str | None
    matching_frames: int
    faces_seen: int
    head_turn: float  # amplitude dans le sens demandé (degrés)
    opposite_turn: float  # amplitude dans le sens opposé


def decide(
    faces: list[FaceObservation | None],
    templates: list[tuple[str, np.ndarray]],
    *,
    direction: Direction,
    threshold: float,
    min_matching_frames: int,
    min_turn_degrees: float,
    left_is_positive_yaw: bool,
) -> Decision:
    """Le test du vivant est évalué indépendamment de l'identité : son résultat ne dit pas
    si une photo ressemble au titulaire du compte."""
    seen = [f for f in faces if f is not None]
    expected_sign = 1 if (direction == "left") == left_is_positive_yaw else -1
    turn, opposite = head_turn([f.yaw for f in seen], expected_sign)
    # Le mouvement principal doit aller dans le sens demandé (une vidéo qui balaie des deux
    # côtés ne passe pas)
    alive = len(seen) >= min_matching_frames and turn >= min_turn_degrees and turn > opposite

    best_score, matching, winners = None, 0, Counter()
    if templates and seen:
        ids = [template_id for template_id, _ in templates]
        matrix = np.stack([vector for _, vector in templates])
        for face in seen:
            scores = matrix @ face.embedding
            index = int(np.argmax(scores))
            score = float(scores[index])
            best_score = score if best_score is None else max(best_score, score)
            if score >= threshold:
                matching += 1
                winners[ids[index]] += 1

    if not alive:
        reason = "liveness_failed"
    elif matching < min_matching_frames:
        reason = "face_not_recognized"
    else:
        reason = None
    return Decision(
        recognized=reason is None,
        reason=reason,
        best_score=round(best_score, 3) if best_score is not None else None,
        template_id=winners.most_common(1)[0][0] if reason is None and winners else None,
        matching_frames=matching,
        faces_seen=len(seen),
        head_turn=round(turn, 1),
        opposite_turn=round(opposite, 1),
    )


def select_for_enrollment(
    per_frame: list[list[FaceObservation]], *, count: int, min_quality: float
) -> list[FaceObservation]:
    """Choisit les captures d'enrôlement : un seul visage net par image, angles variés."""
    candidates = [
        faces[0] for faces in per_frame if len(faces) == 1 and faces[0].det_score >= min_quality
    ]
    if len(candidates) <= count:
        return candidates
    candidates.sort(key=lambda o: o.yaw)
    step = (len(candidates) - 1) / (count - 1)
    return [candidates[round(i * step)] for i in range(count)]


def same_person(selected: list[FaceObservation], threshold: float) -> bool:
    """À l'enrôlement, toutes les captures retenues doivent montrer la même personne."""
    if len(selected) < 2:
        return True
    matrix = np.stack([o.embedding for o in selected])
    similarities = matrix @ matrix.T
    return bool(similarities.min() >= threshold)
