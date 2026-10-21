from prometheus_client import Counter

UPSTREAM_ERRORS = Counter(
    "bo_upstream_errors_total", "Services interrogés injoignables ou en erreur", ["upstream"]
)
OPERATOR_LOGINS = Counter("bo_operator_logins_total", "Connexions d'opérateurs", ["result"])
