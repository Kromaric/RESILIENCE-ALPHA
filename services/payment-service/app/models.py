"""Tables utilisées par payment-service.

Le schéma de référence est infra/mariadb/init/01-schema.sql ; ces modèles n'en
reprennent que les colonnes utiles au service.
"""

from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db import utcnow

BigId = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    pass


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    phone: Mapped[str] = mapped_column(String(16), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    qr_token: Mapped[str | None] = mapped_column(CHAR(22), unique=True, nullable=True)
    is_probe: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Session(Base):
    """Lecture seule : payment-service vérifie que la session du JWT n'est pas révoquée."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"))
    client_api_id: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16))
    factors: Mapped[str] = mapped_column(String(40))
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class LedgerAccount(Base):
    """Compte de la comptabilité Orbe : compte d'un client ou compte de contrepartie."""

    __tablename__ = "ledger_accounts"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(16))  # client | counterpart
    code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    label: Mapped[str] = mapped_column(String(80))
    balance_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    client_id: Mapped[str | None] = mapped_column(
        ForeignKey("clients.id"), unique=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PayoutAccount(Base):
    __tablename__ = "payout_accounts"

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"))
    label: Mapped[str] = mapped_column(String(80))
    iban_last4: Mapped[str] = mapped_column(CHAR(4))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (CheckConstraint("owner_id <> contact_id"),)

    owner_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), primary_key=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), primary_key=True)
    alias: Mapped[str | None] = mapped_column(String(80), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("payer_id", "idempotency_key"),
        UniqueConstraint("parent_id"),
        CheckConstraint("amount_cents > 0"),
    )

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    reference: Mapped[str] = mapped_column(CHAR(11), unique=True)
    type: Mapped[str] = mapped_column(String(16))  # payment | refund | payout
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"))
    payer_id: Mapped[str] = mapped_column(ForeignKey("clients.id"))
    recipient_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    payout_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("payout_accounts.id", ondelete="SET NULL"), nullable=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(CHAR(3), default="EUR")
    description: Mapped[str | None] = mapped_column(String(140), nullable=True)
    card_brand: Mapped[str | None] = mapped_column(String(16), nullable=True)
    card_last4: Mapped[str | None] = mapped_column(CHAR(4), nullable=True)
    # pending | authorized | declined | failed | refunded | completed
    status: Mapped[str] = mapped_column(String(16))
    decline_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(CHAR(36))
    request_hash: Mapped[str] = mapped_column(CHAR(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class LedgerEntry(Base):
    """Écriture : débit ou crédit d'un compte, toujours par paire pour une opération."""

    __tablename__ = "ledger_entries"
    __table_args__ = (CheckConstraint("amount_cents > 0"),)

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("transactions.id"))
    account_id: Mapped[str] = mapped_column(ForeignKey("ledger_accounts.id"))
    direction: Mapped[str] = mapped_column(String(8))  # debit | credit
    amount_cents: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PaymentRequest(Base):
    __tablename__ = "payment_requests"
    __table_args__ = (
        UniqueConstraint("requester_id", "idempotency_key"),
        CheckConstraint("amount_cents > 0"),
    )

    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True)
    reference: Mapped[str] = mapped_column(CHAR(11), unique=True)
    requester_id: Mapped[str] = mapped_column(ForeignKey("clients.id"))
    payer_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("transactions.id"), unique=True, nullable=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(CHAR(3), default="EUR")
    description: Mapped[str | None] = mapped_column(String(140), nullable=True)
    # pending | paid | declined | cancelled | expired | failed
    status: Mapped[str] = mapped_column(String(16))
    failure_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(CHAR(36))
    request_hash: Mapped[str] = mapped_column(CHAR(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
