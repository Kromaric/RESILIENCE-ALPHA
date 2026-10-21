from pathlib import Path

from pydantic import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from app.vault import SecretStore


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
    # Back-office : audience distincte (un jeton client n'ouvre pas le dashboard, un jeton
    # opérateur ne paie pas)
    bo_jwt_audience: str = "orbe-bo"
    bo_jwt_ttl_seconds: int = 3600
    # Connexion au back-office : identifiant → visage → mot de passe (consigne du sujet)
    bo_pending_seconds: int = 120  # délai pour passer d'une étape à la suivante
    bo_enrollment_seconds: int = 600  # première connexion : temps pour enregistrer son visage
    bo_face_failure_seconds: int = 30  # visage non reconnu : rouge fixe, identifiant bloqué
    bo_success_led_seconds: int = 30  # mot de passe correct : vert fixe
    bo_password_failure_blinks: int = 10  # mot de passe faux : rouge clignotant
    led_blink_period_ms: int = 500
    # Clé de l'ESP8266 (GET /devices/led) : Vault, sinon fichier de secret ; absente = route fermée
    led_device_key_file: Path = Path("/run/secrets/led_device_key")
    led_device_key_name: str = "led_device_key"

    # Second facteur : reconnaissance faciale (notre modèle), CADRAGE §4.2
    face_engine: str = "insightface"  # insightface | fake (tests et développement sans caméra)
    face_model: str = "buffalo_s"  # buffalo_l est plus précis mais ~2× plus lourd en RAM
    face_model_root: Path = Path("/opt/insightface")
    face_det_size: int = 320
    face_threshold: float = 0.40  # similarité cosinus, à calibrer sur l'équipe
    face_min_matching_frames: int = 3
    liveness_min_turn_degrees: float = 8.0  # rotation de la tête dans le sens demandé
    liveness_left_is_positive_yaw: bool = (
        True  # sens du lacet du modèle, à vérifier à la calibration
    )
    # Images de connexion : 12 × 300 ms ≈ 3,3 s, le temps de lire la consigne et de tourner
    login_frames: int = 12  # images attendues (indication pour le front)
    login_interval_ms: int = 300
    login_max_frames: int = 16
    enroll_frames: int = 16
    enroll_max_frames: int = 20
    enroll_templates: int = 5
    enroll_min_templates: int = 3
    enroll_min_quality: float = 0.60
    frame_max_bytes: int = 400_000  # par image (JPEG)
    pending_2fa_seconds: int = 120  # délai pour présenter son visage après le mot de passe
    face_cipher: str = "local"  # local (AES-GCM) | vault (Vault Transit)
    face_key_file: Path = Path("/run/secrets/face_embedding_key")
    face_key_name: str = "face_embedding_key"  # nom de la clé dans Vault
    vault_addr: str = "http://vault:8200"
    vault_token_file: Path = Path("/run/secrets/auth_vault_token")
    vault_transit_key: str = "orbe-face"
    web_client_id: str = "orbe-web"  # application utilisée quand X-Client-Id est absent

    # Protection de la connexion
    lockout_threshold: int = 5
    lockout_minutes: int = 10
    login_rate_per_ip: int = 20  # tentatives par minute et par IP
    register_rate_per_ip: int = 5  # inscriptions par minute et par IP
    hash_concurrency: int = 4  # vérifications argon2 simultanées (borne mémoire et CPU)

    # Secrets : Vault KV v2 si AUTH_VAULT_KV_PATH est renseigné, sinon fichiers /run/secrets
    # (repli aussi pour une clé absente de Vault). Voir app/vault.py.
    vault_kv_path: str | None = None  # ex. secret/data/oorbe/config
    vault_role_id_file: Path = Path("/run/secrets/vault_role_id")  # AppRole (prioritaire)
    vault_secret_id_file: Path = Path("/run/secrets/vault_secret_id")
    vault_approle_mount: str = "approle"
    db_password_key: str = "auth_db_password"  # noqa: S105 — nom de la clé dans Vault, pas un secret

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
