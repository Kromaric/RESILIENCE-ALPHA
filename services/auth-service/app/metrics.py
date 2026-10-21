"""Métriques métier d'auth-service (en plus de celles de l'instrumentator HTTP)."""

from prometheus_client import Counter, Histogram

LOGINS = Counter("auth_logins_total", "Connexions réussies")
LOGIN_FAILURES = Counter(
    "auth_login_failures_total",
    "Échecs de connexion",
    ["reason"],  # invalid_credentials | locked | rate_limited
)
ACCOUNT_LOCKS = Counter("auth_account_locks_total", "Comptes bloqués après trop d'échecs")
API_KEY_FAILURES = Counter("auth_api_key_failures_total", "Clés d'API refusées")
SECOND_FACTOR = Counter(
    "auth_second_factor_total",
    "Vérifications du visage à la connexion",
    ["result"],  # recognized | liveness_failed | face_not_recognized
)
FACE_ENROLLMENTS = Counter("auth_face_enrollments_total", "Enrôlements du visage", ["result"])
FACE_INFERENCE_SECONDS = Histogram(
    "auth_face_inference_seconds",
    "Durée d'analyse d'une série d'images",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8, 15),
)
SESSIONS_REVOKED = Counter("auth_sessions_revoked_total", "Sessions révoquées", ["reason"])
REGISTRATIONS = Counter("auth_registrations_total", "Inscriptions", ["result"])
