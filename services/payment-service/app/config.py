from pathlib import Path

from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from app.vault import SecretStore


class Settings(BaseSettings):
    """Configuration lue dans l'environnement (préfixe PAYMENT_).

    Les secrets (mot de passe DB) sont lus dans des fichiers montés en secrets Docker.
    """

    model_config = SettingsConfigDict(env_prefix="PAYMENT_", extra="ignore")

    service_name: str = "payment-service"
    log_level: str = "INFO"
    enable_docs: bool = False

    # Base de données — PAYMENT_DATABASE_URL prend le pas sur les champs détaillés
    database_url: str | None = None
    db_host: str = "mariadb"
    db_port: int = 3306
    db_name: str = "orbe"
    db_user: str = "payment_svc"
    db_password_file: Path = Path("/run/secrets/payment_db_password")
    # Pool volontairement borné : c'est la ressource critique du scénario SC-01 (CADRAGE §4.3)
    db_pool_size: int = 10
    db_pool_timeout: float = 2.0

    # Vérification locale des JWT émis par auth-service
    jwt_public_key_file: Path = Path("/run/secrets/jwt_public_key")
    jwt_issuer: str = "orbe-auth"
    jwt_audience: str = "orbe"

    # Règles métier
    max_amount_cents: int = 50_000  # 500 € par opération
    # Paiements (et créations de demandes) par minute et par client ; 0 désactive la limite.
    # Interagit avec le scénario SC-01 : valeur à régler avec l'équipe Red Team.
    pay_rate_per_client: int = 10
    max_pending_requests: int = 20
    request_ttl_days: int = 7
    max_payout_accounts: int = 5
    max_contacts: int = 200
    # Statut de session (révocation) mis en cache pour ne pas consommer une connexion du pool
    # à chaque requête : une révocation prend effet en au plus ce délai
    session_cache_seconds: float = 5.0

    # Simulation du réseau d'autorisation (connexion DB conservée pendant l'attente)
    authorization_min_ms: int = 50
    authorization_max_ms: int = 150

    # Réconciliation des paiements restés « pending »
    reconcile_enabled: bool = True
    reconcile_after_seconds: int = 30
    reconcile_interval_seconds: float = 15.0

    # Secrets : Vault KV v2 si PAYMENT_VAULT_KV_PATH est renseigné, sinon fichiers /run/secrets
    # (repli aussi pour une clé absente de Vault). Voir app/vault.py.
    vault_kv_path: str | None = None  # ex. secret/data/oorbe/config
    vault_role_id_file: Path = Path("/run/secrets/vault_role_id")  # AppRole (prioritaire)
    vault_secret_id_file: Path = Path("/run/secrets/vault_secret_id")
    vault_approle_mount: str = "approle"
    db_password_key: str = "payment_db_password"  # noqa: S105 — nom de la clé dans Vault, pas un secret
    vault_addr: str = "http://vault:8200"
    vault_token_file: Path = Path("/run/secrets/vault_token")

    _secrets: SecretStore | None = PrivateAttr(default=None)

    def load_secrets(self, transport=None) -> None:
        """Lit Vault une fois (sans effet si vault_kv_path est vide)."""
        self._secrets = SecretStore.load(
            addr=self.vault_addr,
            kv_path=self.vault_kv_path,
            token_file=self.vault_token_file,
            role_id_file=self.vault_role_id_file,
            secret_id_file=self.vault_secret_id_file,
            approle_mount=self.vault_approle_mount,
            transport=transport,
        )

    def secret(self, key: str, file: Path) -> str:
        if self._secrets is None:
            self.load_secrets()
        return self._secrets.get(key, file)

    def sqlalchemy_url(self) -> str | URL:
        if self.database_url:
            return self.database_url
        return URL.create(
            "mysql+aiomysql",
            username=self.db_user,
            password=self.secret(self.db_password_key, self.db_password_file),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )
