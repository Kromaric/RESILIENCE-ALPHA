"""Chargement des CSV de collecte (partagé par train.py et evaluate.py)."""

from __future__ import annotations

import glob
from pathlib import Path

import pandas as pd

NORMAL_LABELS = {"nominal", "peak", "offpeak"}
META_COLUMNS = ["ts", "time", "label", "episode"]
WARMUP_ROWS = 6  # 30 s : fenêtre glissante pas encore remplie en début d'épisode


def load(patterns: list[str], warmup: int = WARMUP_ROWS) -> pd.DataFrame:
    files = sorted({f for p in patterns for f in glob.glob(p)})
    if not files:
        raise SystemExit(f"Aucun CSV ne correspond à : {' '.join(patterns)}")
    frames = []
    for f in files:
        df = pd.read_csv(f)
        df["episode"] = df.get("episode", Path(f).stem)
        frames.append(df.sort_values("ts").iloc[warmup:])
    return pd.concat(frames, ignore_index=True)


def is_normal(df: pd.DataFrame) -> pd.Series:
    return df["label"].isin(NORMAL_LABELS)
