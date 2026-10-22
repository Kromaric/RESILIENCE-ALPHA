"""Rejoue des épisodes étiquetés NON VUS à l'entraînement et calibre le seuil d'alerte.

    python ml/evaluate.py "ml/data/eval/*.csv" --write

Reproduit la règle d'alerte Prometheus : score > seuil pendant `for: 10s`, évalué toutes les
5 s (= 3 évaluations consécutives). Pour chaque épisode :
- normal (nominal / peak / offpeak) : y a-t-il une fausse alerte ? quelle part du temps ?
- attaque (sc01…) : détectée ? délai entre le début de l'épisode et l'alerte ?

Seuil retenu = plus petit seuil sans aucune fausse alerte sur les épisodes normaux + marge,
borné à [0.5, 0.95]. `--write` l'enregistre dans le modèle (detector-ml le publie ensuite
dans `anomaly_threshold`, utilisé par la règle d'alerte).

Sorties : ml/reports/evaluation.md + evaluation.svg (pour le dossier technique).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from anomaly.features import STEP_SECONDS  # noqa: E402
from anomaly.model import AnomalyModel  # noqa: E402
from common import NORMAL_LABELS, load  # noqa: E402

ROOT = Path(__file__).resolve().parent


def sustained(scores: np.ndarray, k: int) -> np.ndarray:
    """Score minimal sur les k dernières évaluations (alerte si > seuil)."""
    return pd.Series(scores).rolling(k, min_periods=k).min().fillna(0).to_numpy()


def attack_start(ep: pd.DataFrame) -> int:
    if "attack_start_ts" in ep and ep["attack_start_ts"].notna().any():
        return int(ep["attack_start_ts"].dropna().iat[0])
    return int(ep["ts"].iat[0])


def episode_result(ep: pd.DataFrame, held: np.ndarray, threshold: float) -> dict:
    alarm = held > threshold
    first = int(np.argmax(alarm)) if alarm.any() else None
    return {
        "episode": ep["episode"].iat[0],
        "label": ep["label"].iat[0],
        "duration_s": len(ep) * STEP_SECONDS,
        "max_score": round(float(ep["score"].max()), 3),
        "alert": bool(alarm.any()),
        "alert_time_pct": round(100 * float(alarm.mean()), 1),
        # délai depuis le lancement de l'attaque (colonne attack_start_ts si connue, sinon
        # début de l'épisode = --start de collect.py)
        "delay_s": None if first is None else int(ep["ts"].iat[first]) - attack_start(ep),
    }


def evaluate(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    return pd.DataFrame(
        episode_result(ep, ep["held"].to_numpy(), threshold)
        for _, ep in df.groupby("episode", sort=False)
    )


def summary(res: pd.DataFrame, threshold: float) -> dict:
    normal = res[res["label"].isin(NORMAL_LABELS)]
    attack = res[~res["label"].isin(NORMAL_LABELS)]
    delays = attack.loc[attack["alert"], "delay_s"]
    return {
        "threshold": round(threshold, 2),
        "false_alert_episodes": int(normal["alert"].sum()),
        "normal_episodes": len(normal),
        "detected_attacks": int(attack["alert"].sum()),
        "attack_episodes": len(attack),
        "median_delay_s": None if delays.empty else float(delays.median()),
        "max_delay_s": None if delays.empty else float(delays.max()),
    }


def plot(df: pd.DataFrame, threshold: float, out: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    episodes = list(df.groupby("episode", sort=False))
    fig, axes = plt.subplots(
        len(episodes), 1, figsize=(10, 1.8 * len(episodes)), sharey=True, squeeze=False
    )
    for ax, (name, ep) in zip(axes[:, 0], episodes, strict=True):
        t = np.arange(len(ep)) * STEP_SECONDS
        attack = ep["label"].iat[0] not in NORMAL_LABELS
        ax.plot(t, ep["score"], color="#c0392b" if attack else "#2c6e9b", lw=1.2)
        ax.axhline(threshold, color="#555", ls="--", lw=0.8)
        ax.fill_between(t, 0, 1, where=ep["held"] > threshold, color="#e74c3c", alpha=0.15)
        ax.set_ylim(0, 1.02)
        ax.set_title(f"{name} ({ep['label'].iat[0]})", fontsize=9, loc="left")
        ax.tick_params(labelsize=8)
    axes[-1, 0].set_xlabel("secondes depuis le début de l'épisode")
    fig.supylabel("anomaly_score")
    fig.tight_layout()
    fig.savefig(out, format="svg")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("data", nargs="+", help="CSV d'évaluation (motifs glob acceptés)")
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "model-payment.joblib")
    parser.add_argument("--for-seconds", type=int, default=10, help="`for:` de la règle")
    parser.add_argument("--margin", type=float, default=0.05)
    parser.add_argument("--write", action="store_true", help="enregistrer le seuil retenu")
    parser.add_argument("--report-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()

    model = AnomalyModel.load(args.model)
    df = load(args.data, warmup=0)  # le délai de détection inclut le remplissage de fenêtre
    seen = set(df["episode"]) & set(model.meta.get("episodes", []))
    if seen:
        print(f"⚠ épisodes déjà vus à l'entraînement (résultats optimistes) : {sorted(seen)}")
    if not df["label"].isin(NORMAL_LABELS).any():
        raise SystemExit("Il faut au moins un épisode normal (nominal/peak) pour calibrer.")

    k = args.for_seconds // STEP_SECONDS + 1
    df["score"] = model.score(df[model.features].to_numpy(dtype=float))
    df["held"] = np.concatenate(
        [sustained(ep["score"].to_numpy(), k) for _, ep in df.groupby("episode", sort=False)]
    )

    worst_normal = float(df.loc[df["label"].isin(NORMAL_LABELS), "held"].max())
    threshold = float(np.clip(worst_normal + args.margin, 0.5, 0.95))
    sweep = pd.DataFrame(
        summary(evaluate(df, t), t) for t in np.round(np.arange(0.5, 0.96, 0.05), 2)
    )
    chosen = summary(evaluate(df, threshold), threshold)
    episodes = evaluate(df, threshold)

    args.report_dir.mkdir(parents=True, exist_ok=True)
    plot(df, threshold, args.report_dir / "evaluation.svg")
    report = [
        "# Évaluation du modèle payment-service\n",
        *(["> ⚠ **Données fictives** (`ml/synth.py`) : résultats de mise au point, pas une "
           "mesure sur la plateforme.\n"] if model.meta.get("synthetic") else []),
        f"Modèle : `{args.model.name}` · {len(model.features)} variables · règle "
        f"`score > seuil` pendant {args.for_seconds} s ({k} évaluations à {STEP_SECONDS} s)\n",
        f"Pire score soutenu en trafic normal : **{worst_normal:.3f}** → seuil retenu "
        f"**{threshold:.2f}** (marge {args.margin})\n",
        "## Seuil retenu\n",
        pd.DataFrame([chosen]).to_markdown(index=False),
        "\n## Par épisode\n",
        episodes.to_markdown(index=False),
        "\n## Balayage des seuils\n",
        sweep.to_markdown(index=False),
        "\n![Scores par épisode](evaluation.svg)\n",
    ]
    (args.report_dir / "evaluation.md").write_text("\n".join(report), encoding="utf-8")

    print(episodes.to_string(index=False))
    print(f"\nSeuil retenu {threshold:.2f} → {json.dumps(chosen, ensure_ascii=False)}")
    if chosen["detected_attacks"] < chosen["attack_episodes"]:
        print("⚠ attaque(s) non détectée(s) : voir le rapport avant de valider le seuil.")

    if args.write:
        model.threshold = round(threshold, 2)
        model.meta["evaluation"] = chosen
        model.save(args.model)
        sidecar = args.model.with_suffix(".json")
        if sidecar.exists():
            info = json.loads(sidecar.read_text(encoding="utf-8"))
            info |= {"threshold": model.threshold, "evaluation": chosen}
            sidecar.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Seuil {model.threshold} enregistré dans {args.model}")


if __name__ == "__main__":
    main()
