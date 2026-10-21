"""Entraîne le modèle payment-service sur du trafic NORMAL uniquement.

    python ml/train.py "ml/data/raw/nominal-*.csv" "ml/data/raw/peak-*.csv"

Les lignes étiquetées attaque (sc01…) sont ignorées : l'IsolationForest apprend ce qui est
ordinaire, l'attaque n'est vue qu'à l'évaluation. Garder des épisodes normaux À PART pour
evaluate.py (sinon les faux positifs sont sous-estimés).

Sorties : ml/models/model-payment.joblib (chargé par detector-ml) + .json lisible.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import sklearn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from anomaly.features import descriptions, feature_names  # noqa: E402
from anomaly.model import AnomalyModel  # noqa: E402
from common import is_normal, load  # noqa: E402

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data", nargs="+", help="CSV (motifs glob acceptés)")
    parser.add_argument("--out", type=Path, default=ROOT / "models" / "model-payment.joblib")
    parser.add_argument("--n-estimators", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    df = load(args.data)
    df = df[is_normal(df)]
    if len(df) < 100:
        raise SystemExit(f"Seulement {len(df)} lignes normales : collecter au moins ~10 min.")

    candidates = [c for c in feature_names() if c in df.columns]
    constant = [c for c in candidates if df[c].std() < 1e-9]  # aucune information
    features = [c for c in candidates if c not in constant]
    X = df[features].to_numpy(dtype=float)

    model = AnomalyModel.fit(X, features, n_estimators=args.n_estimators, random_state=args.seed)
    train_scores = model.score(X)
    synthetic = bool(df["episode"].astype(str).str.startswith("synth-").any())
    model.meta |= {
        "target": "payment-service",
        "synthetic": synthetic,  # données fictives (ml/synth.py) : à réentraîner sur du réel
        "sklearn": sklearn.__version__,
        "n_samples": len(df),
        "samples_per_label": df["label"].value_counts().to_dict(),
        "episodes": sorted(df["episode"].unique()),
        "dropped_constant": constant,
        "feature_descriptions": {f: descriptions()[f] for f in features},
        "feature_mean": dict(zip(features, np.round(X.mean(axis=0), 4).tolist(), strict=True)),
        "train_score_quantiles": {
            q: round(float(np.quantile(train_scores, float(q))), 3)
            for q in ("0.5", "0.95", "0.99", "1.0")
        },
    }
    model.save(args.out)
    sidecar = args.out.with_suffix(".json")
    sidecar.write_text(
        json.dumps(
            {"features": features, "threshold": model.threshold, "df_median": model.df_median,
             "df_min": model.df_min, **model.meta},
            indent=2, ensure_ascii=False, default=str,
        ),
        encoding="utf-8",
    )

    print(f"{len(df)} lignes normales · {len(features)} variables → {args.out}")
    if constant:
        print(f"Variables constantes écartées : {', '.join(constant)}")
    print(f"Score sur l'entraînement : {model.meta['train_score_quantiles']}")
    if synthetic:
        print("⚠ Modèle entraîné sur des données FICTIVES : non valable comme preuve de détection.")
    print("Seuil provisoire 0.7 — lancer ml/evaluate.py pour le calibrer.")


if __name__ == "__main__":
    main()
