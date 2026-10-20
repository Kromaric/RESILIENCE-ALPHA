"""Métriques métier d'auth-service (en plus de celles de l'instrumentator HTTP)."""

from prometheus_client import Counter

LOGINS = Counter("auth_logins_total", "Connexions réussies")
LOGIN_FAILURES = Counter(
    "auth_login_failures_total",
    "Échecs de connexion",
    ["reason"],  # invalid_credentials | locked | rate_limited
)
ACCOUNT_LOCKS = Counter("auth_account_locks_total", "Comptes bloqués après trop d'échecs")
API_KEY_FAILURES = Counter("auth_api_key_failures_total", "Clés d'API refusées")
SECOND_FACTOR = Counter("auth_second_factor_total", "Validations de passkey", ["result"])
PASSKEY_REGISTRATIONS = Counter("auth_passkey_registrations_total", "Passkeys enregistrées")
SESSIONS_REVOKED = Counter("auth_sessions_revoked_total", "Sessions révoquées", ["reason"])
REGISTRATIONS = Counter("auth_registrations_total", "Inscriptions", ["result"])
