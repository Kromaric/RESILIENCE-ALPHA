"""Données FICTIVES pour entraîner un premier modèle avant le déploiement de la plateforme.

    python ml/synth.py                     # → ml/data/synth/raw/ (entraînement) + eval/
    python ml/train.py "ml/data/synth/raw/*.csv" --out ml/models/model-payment.joblib
    python ml/evaluate.py "ml/data/synth/eval/*.csv" --write

But : faire tourner detector-ml, l'alerte et le moteur de remédiation dès maintenant. Ce
modèle ne prouve PAS que la détection marche sur la plateforme (le sujet demande des
données « issues de l'environnement ») : le réentraîner sur les données collectées dès que
payment-service reçoit du trafic. Les épisodes sont préfixés `synth-` et le modèle est
marqué `synthetic: true` (train.py, journaux de detector-ml).

Modèle de simulation (pas un tirage indépendant par variable : les variables sont liées
comme dans le vrai service) :
- arrivées λ(t) (req/s) en marche aléatoire autour du profil, + la sonde (≈ 0,2 req/s) ;
- pool de 10 connexions (config payment-service) ; occupation moyenne par la loi de Little :
  paiement ≈ 130 ms de connexion (autorisation simulée 50-150 ms), lecture ≈ 12 ms ;
- au-delà de la capacité : file d'attente, `pool_timeout` 2 s → 503, p95 ≈ 2 s ;
- CPU / mémoire du conteneur proportionnels à la charge ; CPU hôte bruité (mesuré : ≈ 0,4
  ± 0,15 au repos sur le PC Hôte, d'autres processus tournent) ;
- IP : population de clients légitimes ; SC-01 ajoute 1 à 3 IP qui envoient en masse des
  POST /pay, dont une partie sans jeton valide (401).
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

STEP = 5
POOL_SIZE = 10
PAY_HOLD_S, READ_HOLD_S = 0.13, 0.012
PROBE_RPS = 0.2
ROOT = Path(__file__).resolve().parent


@dataclass
class Profile:
    rps: float  # débit légitime moyen
    pay_share: float = 0.15
    attack_rps: float = 0.0  # SC-01
    attack_ips: int = 0
    attack_unauth: float = 0.0  # part des requêtes d'attaque refusées en 401
    attack_start_s: int = 20  # trafic normal avant le lancement de l'attaque


PROFILES = {
    "offpeak": Profile(rps=0.3),
    "nominal": Profile(rps=3.0),
    "peak": Profile(rps=14.0),  # pic légitime : charge ×5, pool sollicité, pas de saturation
}


def random_walk(rng, n: int, mean: float, rel_sigma: float = 0.08, rho: float = 0.95):
    """Processus AR(1) log-normal : variations lentes et réalistes autour de `mean`."""
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = rho * x[i - 1] + rng.normal(0, rel_sigma)
    return mean * np.exp(x - x.mean())


def simulate(p: Profile, n: int, rng: np.random.Generator) -> pd.DataFrame:
    t = np.arange(n) * STEP
    legit = random_walk(rng, n, p.rps) + PROBE_RPS
    attack = np.where(t >= p.attack_start_s, p.attack_rps, 0.0)
    attack *= np.clip((t - p.attack_start_s + STEP) / 10, 0, 1)  # montée en ~10 s
    attack *= rng.uniform(0.85, 1.15, n)
    total = legit + attack

    # Requêtes qui atteignent la base : l'attaque cible POST /pay, les 401 s'arrêtent avant
    pay = legit * p.pay_share + attack * (1 - p.attack_unauth)
    read = legit * (1 - p.pay_share)
    load = pay * PAY_HOLD_S + read * READ_HOLD_S  # connexions occupées en moyenne
    rho = load / POOL_SIZE
    overflow = np.clip(rho - 0.97, 0, None) / np.maximum(rho, 1e-9)  # part refusée (503)

    in_use = np.minimum(POOL_SIZE, rng.poisson(np.minimum(load, POOL_SIZE * 1.5)))
    base_p95 = 0.12 + rng.normal(0, 0.01, n)  # p95 dominé par l'autorisation (≤ 150 ms)
    queue = 1 / np.clip(1 - np.minimum(rho, 0.97), 0.03, 1)
    p95 = np.where(overflow > 0.02, 2.0 + rng.normal(0, 0.05, n), base_p95 * queue ** 0.5)

    # Ratios = comptes sur la fenêtre de 30 s (tirage binomial : bruit réaliste à faible débit)
    window_n = np.maximum(1, rng.poisson(total * 30))

    def ratio(p_: np.ndarray) -> np.ndarray:
        return rng.binomial(window_n, np.clip(p_, 0, 1)) / window_n

    err5 = ratio(overflow)
    unauth_p = (legit * 0.015 + attack * p.attack_unauth) / total
    rate_limited = attack * (1 - p.attack_unauth) * 0.3  # 429 : limite par client
    client4 = ratio(unauth_p + (legit * 0.03 + rate_limited) / total)
    unauth = ratio(unauth_p)

    # IP sources (fenêtre 30 s) : chaque client légitime fait ~1 requête / 5 s
    legit_ips = np.maximum(1, rng.poisson(np.minimum(legit * 30 / 6, 200)))
    att_ips = np.where(attack > 0, p.attack_ips, 0)
    top_legit = legit / legit_ips * rng.uniform(1.5, 3, n)  # un client un peu plus actif
    top = np.maximum(top_legit, np.where(att_ips > 0, attack / np.maximum(att_ips, 1), 0))

    return pd.DataFrame({
        "req_rate": total,
        "latency_p95": np.clip(p95, 0.01, None),
        "error_5xx_ratio": err5,
        "client_4xx_ratio": client4,
        "pool_saturation": in_use / POOL_SIZE,
        "pool_timeouts_rate": np.clip(overflow * total + rng.normal(0, 0.01, n), 0, None),
        "container_cpu": np.clip(0.015 + 0.011 * total + rng.normal(0, 0.008, n), 0, 1.5),
        "container_mem_mib": 85 + 0.6 * np.minimum(total, 80) + rng.normal(0, 1.5, n),
        "host_cpu": np.clip(random_walk(rng, n, 0.38, 0.25, 0.8) + 0.004 * total, 0, 1),
        "ip_distinct": (legit_ips + att_ips).astype(float),
        "ip_top_share": np.clip(top / total, 0, 1),
        "unauth_ratio": unauth,
    })


def episode(label: str, name: str, p: Profile, minutes: float, rng, t0: int) -> pd.DataFrame:
    n = int(minutes * 60 / STEP)
    df = simulate(p, n, rng).round(5)
    df.insert(0, "ts", t0 + STEP * np.arange(n))
    df.insert(1, "time", pd.to_datetime(df["ts"], unit="s", utc=True))
    df.insert(2, "label", label)
    df.insert(3, "episode", name)
    if p.attack_rps:
        df["attack_start_ts"] = t0 + p.attack_start_s
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "synth")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = np.random.default_rng(args.seed)
    t0 = int(time.time()) - 7 * 86400
    t0 -= t0 % STEP

    plan = [  # (dossier, étiquette, profil, minutes, nombre d'épisodes)
        ("raw", "nominal", PROFILES["nominal"], 30, 3),
        ("raw", "peak", PROFILES["peak"], 30, 2),
        ("raw", "offpeak", PROFILES["offpeak"], 30, 1),
        ("eval", "nominal", PROFILES["nominal"], 20, 1),
        ("eval", "peak", Profile(rps=18.0), 20, 1),  # pic un peu plus fort que l'entraînement
        ("eval", "offpeak", PROFILES["offpeak"], 10, 1),
    ]
    # SC-01 : intensités variées (dont une attaque faible, plus dure à voir), 3 min chacune
    attacks = [Profile(rps=3.0, attack_rps=r, attack_ips=k, attack_unauth=u)
               for r, k, u in [(120, 1, 0.3), (90, 2, 0.5), (150, 3, 0.2), (70, 1, 0.4),
                               (80, 1, 0.1)]]

    for d in ("raw", "eval"):
        (args.out / d).mkdir(parents=True, exist_ok=True)
    count = {}
    for folder, label, prof, minutes, k in plan:
        for _ in range(k):
            count[label] = count.get(label, 0) + 1
            name = f"synth-{label}-{count[label]:02d}"
            episode(label, name, prof, minutes, rng, t0).to_csv(
                args.out / folder / f"{name}.csv", index=False)
            t0 += int(minutes * 60) + 600
    for i, prof in enumerate(attacks, 1):
        name = f"synth-sc01-{i:02d}"
        episode("sc01", name, prof, 3, rng, t0).to_csv(args.out / "eval" / f"{name}.csv",
                                                       index=False)
        t0 += 780
    print(f"Données fictives → {args.out}/raw (entraînement) et {args.out}/eval (évaluation)")


if __name__ == "__main__":
    main()
