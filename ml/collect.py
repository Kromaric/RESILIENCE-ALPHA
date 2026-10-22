"""Extrait de Prometheus et Loki les vecteurs de variables d'une période, en CSV étiqueté.

Les deux bases gardent l'historique : on joue d'abord un profil de trafic (Locust, attaque
SC-01…), puis on « rembobine » la période jouée. Une ligne toutes les 5 s.

    # juste après un run Locust de 30 min en profil nominal
    python ml/collect.py --label nominal --since 30m

    # une attaque SC-01 jouée entre 10:02 et 10:05 (heure locale)
    python ml/collect.py --label sc01 --start 2026-10-22T10:02:00 --end 2026-10-22T10:05:00

Étiquettes : `nominal`, `peak` (pic légitime), `offpeak` (heures creuses) = trafic normal ;
toute autre étiquette (`sc01`, `sc02`…) = épisode d'attaque, utilisé seulement par evaluate.py.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from anomaly.sources import Sources  # noqa: E402

ROOT = Path(__file__).resolve().parent
CHUNK_SECONDS = 3600  # < 11 000 points par série et par requête


def parse_duration(text: str) -> int:
    match = re.fullmatch(r"(\d+)([smh])", text)
    if not match:
        raise argparse.ArgumentTypeError("durée attendue : 90s, 30m, 2h…")
    return int(match[1]) * {"s": 1, "m": 60, "h": 3600}[match[2]]


def parse_time(text: str) -> int:
    # sans fuseau → heure locale du poste
    return int(datetime.fromisoformat(text).astimezone().timestamp())


async def fetch(sources: Sources, start: int, end: int) -> list[dict]:
    rows: list[dict] = []
    t = start
    while t <= end:
        chunk_end = min(t + CHUNK_SECONDS, end)
        rows += await sources.history(t, chunk_end)
        t = chunk_end + 5
    await sources.aclose()
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--label", required=True, help="nominal | peak | offpeak | sc01 …")
    period = parser.add_mutually_exclusive_group(required=True)
    period.add_argument("--since", type=parse_duration, help="période écoulée (ex. 30m)")
    period.add_argument("--start", type=parse_time, help="début ISO, heure locale")
    parser.add_argument("--end", type=parse_time, help="fin ISO (défaut : maintenant)")
    parser.add_argument("--prometheus", default="http://localhost:9090")
    parser.add_argument("--loki", default="http://localhost:3100")
    parser.add_argument("--no-loki", action="store_true", help="variables Prometheus seules")
    parser.add_argument("--out", type=Path, help="CSV de sortie (défaut : ml/data/raw/…)")
    args = parser.parse_args()

    end = args.end or int(time.time())
    start = end - args.since if args.since else args.start
    if start >= end:
        parser.error("la période est vide")

    stamp = datetime.fromtimestamp(start).strftime("%Y%m%d-%H%M")
    out = args.out or ROOT / "data" / "raw" / f"{args.label}-{stamp}.csv"
    sources = Sources(args.prometheus, None if args.no_loki else args.loki, timeout=30)
    rows = asyncio.run(fetch(sources, start, end))

    df = pd.DataFrame(rows)
    df.insert(1, "time", pd.to_datetime(df["ts"], unit="s", utc=True))
    df.insert(2, "label", args.label)
    df.insert(3, "episode", out.stem)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)

    feats = df.drop(columns=["ts", "time", "label", "episode"])
    silent = [c for c in feats if feats[c].eq(0).all()]
    print(f"{len(df)} lignes → {out}")
    if silent:
        print(f"⚠ variables toujours à 0 (source absente ?) : {', '.join(silent)}")


if __name__ == "__main__":
    main()
