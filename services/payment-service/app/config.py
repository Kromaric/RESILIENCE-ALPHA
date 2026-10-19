from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


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
    max_amount_cents: int = 500_000  # 5 000 €
    # Paiements (et créations de demandes) par minute et par client ; 0 désactive la limite.
    # Interagit avec le scénario SC-01 : valeur à régler avec l'équipe Red Team.
    pay_rate_per_client: int = 10
    max_pending_requests: int = 20
    request_ttl_days: int = 7

    # Simulation du réseau d'autorisation (connexion DB conservée pendant l'attente)
    authorization_min_ms: int = 50
    authorization_max_ms: int = 150

    # Réconciliation des paiements restés « pending »
    reconcile_enabled: bool = True
    reconcile_after_seconds: int = 30
    reconcile_interval_seconds: float = 15.0

    def sqlalchemy_url(self) -> str | URL:
        if self.database_url:
            return self.database_url
        return URL.create(
            "mysql+aiomysql",
            username=self.db_user,
            password=self.db_password_file.read_text(encoding="utf-8").strip(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )
