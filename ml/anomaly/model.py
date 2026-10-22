"""Modèle de détection : StandardScaler + IsolationForest, score normalisé dans [0, 1].

Normalisation du score (calculée sur le jeu d'entraînement, donc du trafic normal) :

    score = 0.5 × (médiane_train − decision_function) / (médiane_train − minimum_train)

- 0    : aussi « typique » que la moitié du trafic normal (ou plus) ;
- 0.5  : aussi atypique que le point le plus extrême vu en trafic normal ;
- 1    : deux fois plus loin que ce point (plafonné).

Le seuil d'alerte est ensuite choisi par `ml/evaluate.py` sur des épisodes non vus.

Note : l'IsolationForest est insensible à une mise à l'échelle linéaire de chaque variable ;
le StandardScaler sert à l'explicabilité (z-scores de `top_deviations`), pas à la détection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

DEFAULT_THRESHOLD = 0.7


@dataclass
class AnomalyModel:
    pipeline: Pipeline
    features: list[str]
    df_median: float
    df_min: float
    threshold: float = DEFAULT_THRESHOLD
    meta: dict = field(default_factory=dict)

    # --- Entraînement --------------------------------------------------------------------------
    @classmethod
    def fit(
        cls,
        X: np.ndarray,
        features: list[str],
        n_estimators: int = 200,
        random_state: int = 42,
    ) -> AnomalyModel:
        pipeline = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "forest",
                    IsolationForest(
                        n_estimators=n_estimators,
                        max_samples="auto",
                        contamination="auto",  # le seuil est calibré à part (evaluate.py)
                        random_state=random_state,
                    ),
                ),
            ]
        )
        pipeline.fit(X)
        df = pipeline.decision_function(X)
        return cls(
            pipeline=pipeline,
            features=list(features),
            df_median=float(np.median(df)),
            df_min=float(df.min()),
            meta={"trained_at": datetime.now(UTC).isoformat(timespec="seconds")},
        )

    # --- Inférence ----------------------------------------------------------------------------
    def score(self, X: np.ndarray) -> np.ndarray:
        df = self.pipeline.decision_function(np.atleast_2d(X))
        span = max(self.df_median - self.df_min, 1e-9)
        return np.clip(0.5 * (self.df_median - df) / span, 0.0, 1.0)

    def vector(self, row: dict[str, float]) -> np.ndarray:
        return np.array([[row.get(name, 0.0) for name in self.features]], dtype=float)

    def zscores(self, X: np.ndarray) -> np.ndarray:
        return self.pipeline.named_steps["scaler"].transform(np.atleast_2d(X))

    def top_deviations(self, row: dict[str, float], k: int = 3) -> list[dict]:
        """Variables les plus éloignées de leur moyenne d'entraînement (explicabilité)."""
        scaler = self.pipeline.named_steps["scaler"]
        z = self.zscores(self.vector(row))[0]
        order = np.argsort(-np.abs(z))[:k]
        return [
            {
                "feature": self.features[i],
                "value": round(float(row.get(self.features[i], 0.0)), 4),
                "normal_mean": round(float(scaler.mean_[i]), 4),
                "zscore": round(float(z[i]), 2),
            }
            for i in order
        ]

    # --- Persistance --------------------------------------------------------------------------
    # Dictionnaire simple (pas d'objet maison picklé) : chargeable même si ce module évolue.
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "pipeline": self.pipeline,
                "features": self.features,
                "df_median": self.df_median,
                "df_min": self.df_min,
                "threshold": self.threshold,
                "meta": self.meta,
            },
            path,
        )

    @classmethod
    def load(cls, path: Path) -> AnomalyModel:
        return cls(**joblib.load(path))
