"""Métriques métier de payment-service (en plus de celles de l'instrumentator HTTP).

Les métriques du pool alimentent directement le modèle de détection (CADRAGE §6.5).
"""

from prometheus_client import Counter, Gauge, Histogram

TRANSACTIONS = Counter("payment_transactions_total", "Opérations traitées", ["type", "status"])
DECLINES = Counter("payment_declines_total", "Paiements refusés", ["reason"])
REQUESTS = Counter("payment_requests_total", "Demandes d'argent", ["status"])
AUTHORIZATION_SECONDS = Histogram(
    "payment_authorization_seconds",
    "Durée de l'autorisation simulée (connexion DB conservée)",
    buckets=(0.025, 0.05, 0.1, 0.15, 0.25, 0.5, 1, 2, 5),
)
POOL_IN_USE = Gauge("payment_db_pool_in_use", "Connexions du pool actuellement utilisées")
POOL_SIZE = Gauge("payment_db_pool_size", "Taille du pool de connexions")
POOL_TIMEOUTS = Counter(
    "payment_db_pool_timeouts_total", "Requêtes refusées faute de connexion disponible"
)
DB_ERRORS = Counter("payment_db_errors_total", "Erreurs de connexion à la base")
RECONCILED = Counter(
    "payment_reconciled_total", "Paiements « pending » passés en échec par la réconciliation"
)


def bind_pool_metrics(pool) -> None:
    """Relie les jauges au pool SQLAlchemy (QueuePool en production)."""
    if hasattr(pool, "checkedout"):
        POOL_IN_USE.set_function(pool.checkedout)
    if hasattr(pool, "size"):
        POOL_SIZE.set_function(pool.size)
