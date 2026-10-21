"""Tables utilisées par auth-service.

Le schéma de référence est infra/mariadb/init/01-schema.sql ; ces modèles n'en
reprennent que les colonnes utiles au service.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    false,
    func,
    true,
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
    biometric_consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
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


class ClientFaceTemplate(Base):
    """Gabarit facial d'un client : embedding chiffré, lié à son titulaire. Aucune image."""

    __tablename__ = "client_face_templates"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))
    embedding_ct: Mapped[str] = mapped_column(String(4096))
    embedding_dim: Mapped[int] = mapped_column(Integer, default=512)
    model: Mapped[str] = mapped_column(String(40))
    quality_score: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Session(Base):
    """Session ouverte après authentification ; son identifiant est le `jti` du JWT."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"))
    client_api_id: Mapped[str] = mapped_column(ForeignKey("client_apis.id"))
    face_template_id: Mapped[str | None] = mapped_column(
        ForeignKey("client_face_templates.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16))  # pending_2fa | active | revoked | expired
    factors: Mapped[str] = mapped_column(String(40))  # « pwd » ou « pwd,face »
    challenge: Mapped[str | None] = mapped_column(String(16), nullable=True)  # left | right
    face_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    @property
    def factor_list(self) -> list[str]:
        return self.factors.split(",") if self.factors else []


class Operator(Base):
    """Opérateur du back-office (dashboard). Créé par un administrateur (rôle admin)."""

    __tablename__ = "operators"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    # Valeurs par défaut aussi côté base : la création n'insère que les colonnes autorisées
    role: Mapped[str] = mapped_column(
        String(16), default="viewer", server_default="viewer"
    )  # viewer | operator | admin
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    biometric_consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, server_default=func.current_timestamp()
    )


class OperatorFaceTemplate(Base):
    """Gabarit facial d'un opérateur : embedding chiffré (« operator:<id> » en donnée liée)."""

    __tablename__ = "operator_face_templates"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    operator_id: Mapped[str] = mapped_column(ForeignKey("operators.id", ondelete="CASCADE"))
    embedding_ct: Mapped[str] = mapped_column(String(4096))
    embedding_dim: Mapped[int] = mapped_column(Integer, default=512)
    model: Mapped[str] = mapped_column(String(40))
    quality_score: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class OperatorSession(Base):
    """Session du back-office ; son identifiant est le `jti` du JWT d'audience orbe-bo."""

    __tablename__ = "operator_sessions"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    # None : identifiant inconnu (la connexion échouera au visage, sans le révéler)
    operator_id: Mapped[str | None] = mapped_column(
        ForeignKey("operators.id", ondelete="CASCADE"), nullable=True
    )
    # pending_face | pending_password | enrollment | active | revoked | expired
    status: Mapped[str] = mapped_column(String(16))
    factors: Mapped[str] = mapped_column(String(40), default="", server_default="")
    challenge: Mapped[str | None] = mapped_column(String(16), nullable=True)  # left | right
    face_template_id: Mapped[str | None] = mapped_column(
        ForeignKey("operator_face_templates.id", ondelete="SET NULL"), nullable=True
    )
    face_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
