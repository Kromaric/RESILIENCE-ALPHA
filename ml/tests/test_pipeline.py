"""Chaîne train → evaluate sur des données SYNTHÉTIQUES (test du code, pas du modèle).

Les résultats à présenter au jury viennent uniquement des données collectées sur la plateforme.

    python -m pytest ml/tests
"""

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ML = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ML))

from anomaly.features import feature_names, loki_features_from_series  # noqa: E402
from anomaly.model import AnomalyModel  # noqa: E402

PROFILES = {  # moyenne de chaque variable par profil
    "nominal": dict(req_rate=2, latency_p95=0.08, error_5xx_ratio=0, client_4xx_ratio=0.05,
                    pool_saturation=0.2, pool_timeouts_rate=0, container_cpu=0.1,
                    container_mem_mib=120, host_cpu=0.2, ip_distinct=30, ip_top_share=0.08,
                    unauth_ratio=0.02),
    "peak": dict(req_rate=10, latency_p95=0.15, error_5xx_ratio=0, client_4xx_ratio=0.06,
                 pool_saturation=0.5, pool_timeouts_rate=0, container_cpu=0.4,
                 container_mem_mib=130, host_cpu=0.45, ip_distinct=60, ip_top_share=0.05,
                 unauth_ratio=0.02),
    "sc01": dict(req_rate=25, latency_p95=2.0, error_5xx_ratio=0.5, client_4xx_ratio=0.3,
                 pool_saturation=1.0, pool_timeouts_rate=8, container_cpu=0.9,
                 container_mem_mib=140, host_cpu=0.6, ip_distinct=31, ip_top_share=0.7,
                 unauth_ratio=0.3),
}


def episode(label: str, name: str, n: int, rng, attack_after: int = 0) -> pd.DataFrame:
    rows = []
    for i in range(n):
        base = PROFILES["nominal" if label == "sc01" and i < attack_after else label]
        rows.append({k: max(0.0, v * (1 + rng.normal(0, 0.12)) + abs(rng.normal(0, 0.005)))
                     for k, v in base.items()})
    df = pd.DataFrame(rows)
    df.insert(0, "ts", 1_790_000_000 + 5 * np.arange(n))
    df.insert(1, "time", pd.to_datetime(df["ts"], unit="s", utc=True))
    df.insert(2, "label", label)
    df.insert(3, "episode", name)
    return df


@pytest.fixture()
def dataset(tmp_path):
    rng = np.random.default_rng(0)
    raw, ev = tmp_path / "raw", tmp_path / "eval"
    raw.mkdir()
    ev.mkdir()
    episode("nominal", "nominal-a", 400, rng).to_csv(raw / "nominal-a.csv", index=False)
    episode("peak", "peak-a", 200, rng).to_csv(raw / "peak-a.csv", index=False)
    episode("nominal", "nominal-b", 120, rng).to_csv(ev / "nominal-b.csv", index=False)
    episode("peak", "peak-b", 120, rng).to_csv(ev / "peak-b.csv", index=False)
    for i in range(3):
        episode("sc01", f"sc01-{i}", 40, rng, attack_after=2).to_csv(
            ev / f"sc01-{i}.csv", index=False)
    return tmp_path


def run(*args):
    out = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True,
                         check=False)
    assert out.returncode == 0, out.stderr
    return out.stdout


def test_train_then_evaluate(dataset):
    model_path = dataset / "model.joblib"
    run(ML / "train.py", dataset / "raw" / "*.csv", "--out", model_path)
    model = AnomalyModel.load(model_path)
    assert model.features == feature_names()
    assert model.meta["samples_per_label"].keys() == {"nominal", "peak"}

    run(ML / "evaluate.py", dataset / "eval" / "*.csv", "--model", model_path, "--write",
        "--report-dir", dataset / "reports")
    model = AnomalyModel.load(model_path)
    ev = model.meta["evaluation"]
    assert ev["false_alert_episodes"] == 0  # un pic légitime ne déclenche pas
    assert ev["detected_attacks"] == 3
    assert ev["max_delay_s"] <= 25
    assert (dataset / "reports" / "evaluation.svg").exists()

    deviations = model.top_deviations(PROFILES["sc01"])
    assert {d["feature"] for d in deviations} & {"pool_timeouts_rate", "error_5xx_ratio",
                                                  "latency_p95", "ip_top_share"}


def test_loki_aggregation():
    series = [
        ({"client_ip": "10.0.0.1", "status": "201"}, 8),
        ({"client_ip": "10.0.0.1", "status": "401"}, 2),
        ({"client_ip": "10.0.0.2", "status": "200"}, 10),
        ({"client_ip": "10.0.0.3", "status": "403"}, 0),
    ]
    assert loki_features_from_series(series) == {
        "ip_distinct": 2.0, "ip_top_share": 0.5, "unauth_ratio": 0.1,
    }
    assert loki_features_from_series([])["ip_distinct"] == 0.0
