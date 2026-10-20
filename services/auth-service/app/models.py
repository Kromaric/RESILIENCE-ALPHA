"""Tables utilisées par auth-service.

Le schéma de référence est infra/mariadb/init/01-schema.sql ; ces modèles n'en
reprennent que les colonnes utiles au service.
"""

from datetime import datetime

from sqlalchemy import (
    CHAR,
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db import utcnow


class Base(DeclarativeBase):
    pass


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    phone: Mapped[str] = mapped_column(String(16), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    # Valeurs par défaut côté base : l'inscription n'insère que les colonnes autorisées
    # (droit INSERT par colonne, voir 02-users.sh) ; is_probe ne peut pas être positionné.
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_probe: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, server_default=func.current_timestamp()
    )


class ClientApi(Base):
    """Application qui ouvre les sessions : appli web, partenaire, service (sonde)."""

    __tablename__ = "client_apis"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(16))  # application | partner | service
    key_hash: Mapped[str | None] = mapped_column(CHAR(64), unique=True, nullable=True)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Passkey(Base):
    """Passkey WebAuthn d'un appareil : seule la clé publique est conservée."""

    __tablename__ = "passkeys"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"))
    credential_id: Mapped[str] = mapped_column(String(512), unique=True)  # base64url
    public_key: Mapped[str] = mapped_column(Text)  # clé COSE, base64url
    sign_count: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), default=0)
    device_name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Session(Base):
    """Session ouverte après authentification ; son identifiant est le `jti` du JWT."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"))
    client_api_id: Mapped[str] = mapped_column(ForeignKey("client_apis.id"))
    passkey_id: Mapped[str | None] = mapped_column(ForeignKey("passkeys.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16))  # pending_2fa | active | revoked | expired
    factors: Mapped[str] = mapped_column(String(40))  # « pwd » ou « pwd,passkey »
    webauthn_challenge: Mapped[str | None] = mapped_column(String(128), nullable=True)
    challenge_purpose: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    @property
    def factor_list(self) -> list[str]:
        return self.factors.split(",") if self.factors else []
