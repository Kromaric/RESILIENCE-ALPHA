"""Variables d'entrée du modèle de détection — source unique (CADRAGE §6.5).

Le même module sert à la collecte (`ml/collect.py`, requêtes « range ») et à l'inférence
(`services/detector-ml`, requêtes instantanées) : les variables vues à l'entraînement et en
production sont donc calculées par exactement les mêmes requêtes.

Sélecteurs alignés sur la pile réelle (`infra/`) :
- Prometheus : jobs `payment-service` / `node-exporter`, cAdvisor (label `name` du conteneur).
  L'instrumentator FastAPI groupe les statuts (`status="5xx"`, `"4xx"`…) et n'a pas de label
  `service` : on filtre donc par `job`.
- Loki : Promtail pose les labels `container` et `stream` ; les champs du journal JSON
  (`msg`, `status`, `client_ip`) sont extraits à la requête avec `| json`.

Aucune dépendance lourde : ce module est embarqué tel quel dans l'image de detector-ml.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

WINDOW = "30s"  # fenêtre glissante de chaque variable
STEP_SECONDS = 5  # cadence d'inférence = scrape_interval Prometheus

# --- Sélecteurs (à adapter ici seulement si les noms changent) -------------------------------
PAY_JOB = 'job=~"payment-service.*"'
PAY_CONTAINER = 'name=~"oorbe-payment-service.*"'
NODE_JOB = 'job="node-exporter"'
LOKI_PAY_STREAM = '{container=~"oorbe-payment-service.*"}'


@dataclass(frozen=True)
class PromFeature:
    name: str
    query: str
    description: str


def _ratio(numerator: str, denominator: str) -> str:
    # « or vector(0) » : pas de série 5xx tant qu'aucune erreur n'a eu lieu → 0, pas « vide »
    return f"(({numerator}) or vector(0)) / clamp_min(({denominator}), 0.01)"


def prometheus_features(window: str = WINDOW) -> list[PromFeature]:
    w = window
    total = f"sum(rate(http_requests_total{{{PAY_JOB}}}[{w}]))"
    return [
        PromFeature("req_rate", total, "Débit HTTP du service (req/s)"),
        PromFeature(
            "latency_p95",
            "histogram_quantile(0.95, sum by (le) "
            f"(rate(http_request_duration_seconds_bucket{{{PAY_JOB}}}[{w}])))",
            "Latence p95 (s)",
        ),
        PromFeature(
            "error_5xx_ratio",
            _ratio(f'sum(rate(http_requests_total{{{PAY_JOB},status="5xx"}}[{w}]))', total),
            "Part des réponses 5xx",
        ),
        PromFeature(
            "client_4xx_ratio",
            _ratio(f'sum(rate(http_requests_total{{{PAY_JOB},status="4xx"}}[{w}]))', total),
            "Part des réponses 4xx (401/403/422/429)",
        ),
        PromFeature(
            "pool_saturation",
            f"max(payment_db_pool_in_use{{{PAY_JOB}}} / payment_db_pool_size{{{PAY_JOB}}})",
            "Saturation du pool de connexions MariaDB (0-1)",
        ),
        PromFeature(
            "pool_timeouts_rate",
            f"sum(rate(payment_db_pool_timeouts_total{{{PAY_JOB}}}[{w}])) or vector(0)",
            "Requêtes refusées faute de connexion (/s)",
        ),
        PromFeature(
            "container_cpu",
            f"sum(rate(container_cpu_usage_seconds_total{{{PAY_CONTAINER}}}[{w}]))",
            "CPU du conteneur payment-service (cœurs)",
        ),
        PromFeature(
            "container_mem_mib",
            f"sum(container_memory_working_set_bytes{{{PAY_CONTAINER}}}) / 1048576",
            "Mémoire du conteneur payment-service (Mio)",
        ),
        PromFeature(
            "host_cpu",
            f'1 - avg(rate(node_cpu_seconds_total{{{NODE_JOB},mode="idle"}}[{w}]))',
            "CPU de la machine hôte (0-1)",
        ),
    ]


# --- Loki : une seule requête, trois variables ------------------------------------------------
LOKI_FEATURES = {
    "ip_distinct": "Nombre d'IP sources distinctes",
    "ip_top_share": "Part du trafic de l'IP la plus active (0-1)",
    "unauth_ratio": "Part des réponses 401/403",
}


def loki_query(window: str = WINDOW) -> str:
    return (
        f'sum by (client_ip, status) (count_over_time({LOKI_PAY_STREAM} | json '
        f'| __error__="" | msg="request" [{window}]))'
    )


def loki_features_from_series(series: Iterable[tuple[dict, float]]) -> dict[str, float]:
    """Agrège les comptes (client_ip, status) d'un instant en variables."""
    per_ip: dict[str, float] = defaultdict(float)
    total = unauth = 0.0
    for labels, count in series:
        if not count or math.isnan(count):
            continue
        per_ip[labels.get("client_ip", "-")] += count
        total += count
        if str(labels.get("status")) in {"401", "403"}:
            unauth += count
    if total == 0:
        return {"ip_distinct": 0.0, "ip_top_share": 0.0, "unauth_ratio": 0.0}
    return {
        "ip_distinct": float(len(per_ip)),
        "ip_top_share": max(per_ip.values()) / total,
        "unauth_ratio": unauth / total,
    }


def feature_names(use_loki: bool = True) -> list[str]:
    names = [f.name for f in prometheus_features()]
    return names + (list(LOKI_FEATURES) if use_loki else [])


def descriptions() -> dict[str, str]:
    return {f.name: f.description for f in prometheus_features()} | LOKI_FEATURES


def clean(value: float | None) -> float:
    """NaN / ±Inf / absence → 0 (ex. p95 sans trafic). Même règle à la collecte et en ligne."""
    if value is None or math.isnan(value) or math.isinf(value):
        return 0.0
    return float(value)
