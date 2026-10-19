from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Configuration lue dans l'environnement (préfixe AUTH_).

    Les secrets (mot de passe DB, clé privée JWT) sont lus dans des fichiers montés
    en secrets Docker, jamais dans des variables d'environnement en clair.
    """

    model_config = SettingsConfigDict(env_prefix="AUTH_", extra="ignore")

    service_name: str = "auth-service"
    log_level: str = "INFO"
    enable_docs: bool = False

    # Base de données — AUTH_DATABASE_URL prend le pas sur les champs détaillés
    database_url: str | None = None
    db_host: str = "mariadb"
    db_port: int = 3306
    db_name: str = "orbe"
    db_user: str = "auth_svc"
    db_password_file: Path = Path("/run/secrets/auth_db_password")
    db_pool_size: int = 5

    # Jetons
    jwt_private_key_file: Path = Path("/run/secrets/jwt_private_key")
    jwt_issuer: str = "orbe-auth"
    jwt_audience: str = "orbe"
    jwt_ttl_seconds: int = 900

    # Protection de la connexion
    lockout_threshold: int = 5
    lockout_minutes: int = 10
    login_rate_per_ip: int = 20  # tentatives par minute et par IP
    hash_concurrency: int = 4  # vérifications argon2 simultanées (borne mémoire et CPU)

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
