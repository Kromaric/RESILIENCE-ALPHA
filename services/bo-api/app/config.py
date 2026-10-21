from pathlib import Path

from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from app.vault import SecretStore


class Settings(BaseSettings):
    """Configuration lue dans l'environnement (préfixe BO_).

    bo-api ne détient aucun secret d'écriture : la clé publique JWT pour vérifier les jetons
    opérateurs et le mot de passe du compte MariaDB `bo_ro` (lecture seule, clients masqués).
    """

    model_config = SettingsConfigDict(env_prefix="BO_", extra="ignore")

    service_name: str = "bo-api"
    log_level: str = "INFO"
    enable_docs: bool = False
    # Origines autorisées à appeler l'API depuis un navigateur (front Vite en développement).
    # En démonstration, le dashboard et bo-api sont servis sous la même origine (Nginx).
    cors_origins: list[str] = []

    # Jetons opérateurs émis par auth-service (audience distincte de celle des clients)
    jwt_public_key_file: Path = Path("/run/secrets/jwt_public_key")
    jwt_issuer: str = "orbe-auth"
    jwt_audience: str = "orbe-bo"
    # Vérification de la session auprès d'auth-service, mise en cache : délai maximal de
    # prise en compte d'une déconnexion ou d'un compte désactivé
    session_cache_seconds: float = 5.0

    # Base (données applicatives) : compte bo_ro, lecture seule — BO_DATABASE_URL prend le pas
    database_url: str | None = None
    db_host: str = "mariadb"
    db_port: int = 3306
    db_name: str = "orbe"
    db_user: str = "bo_ro"
    db_password_file: Path = Path("/run/secrets/bo_db_password")
    db_pool_size: int = 3  # le back-office ne doit pas concurrencer les services métier
    db_pool_timeout: float = 2.0
    page_size_max: int = 100

    # Services interrogés
    auth_url: str = "http://auth-service:8001"
    prometheus_url: str = "http://prometheus:9090"
    loki_url: str = "http://loki:3100"
    remediation_url: str = "http://remediation-engine:8003"
    detector_url: str = "http://detector-ml:8004"
    assistant_url: str = "http://assistant-rag:8005"
    # Adresse de Grafana vue par le navigateur de l'opérateur (liens et panneaux intégrés)
    grafana_public_url: str = "http://localhost:3000"
    grafana_dashboard_uid: str = "orbe-supervision"
    prometheus_public_url: str = "http://localhost:9090"
    upstream_timeout_seconds: float = 3.0
    assistant_timeout_seconds: float = 60.0  # un LLM local peut mettre plusieurs secondes
    assistant_rate_per_operator: int = 10  # questions par minute et par opérateur

    # Supervision
    display_timezone: str = "Europe/Paris"  # heures affichées sur les graphiques
    payment_job: str = "payment-service"  # job Prometheus des services surveillés
    auth_job: str = "auth-service"
    anomaly_target: str = "payment"  # label target du score d'anomalie (detector-ml)
    # Sélecteur LogQL des journaux affichés (conteneurs de la plateforme)
    loki_selector: str = '{container=~"oorbe-.+"}'
    availability_objective_percent: float = 99.5
    latency_threshold_ms: float = 800.0
    error_rate_threshold: float = 0.02
    anomaly_threshold: float = 0.80
    disk_mountpoint: str = "/"  # Docker Desktop : /var/lib (disque des conteneurs)
    network_reference_bytes_per_second: float = 12_500_000.0  # 100 Mbit/s = 100 % de la jauge

    # Secrets : Vault KV v2 si BO_VAULT_KV_PATH est renseigné, sinon fichiers /run/secrets
    # (repli aussi pour une clé absente de Vault). Voir app/vault.py.
    vault_kv_path: str | None = None  # ex. secret/data/oorbe/config
    vault_role_id_file: Path = Path("/run/secrets/vault_role_id")  # AppRole (prioritaire)
    vault_secret_id_file: Path = Path("/run/secrets/vault_secret_id")
    vault_approle_mount: str = "approle"
    db_password_key: str = "bo_db_password"  # noqa: S105 — nom de la clé dans Vault, pas un secret
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
