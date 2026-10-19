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
    balance_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    qr_token: Mapped[str | None] = mapped_column(CHAR(22), unique=True, nullable=True)
    is_probe: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PayoutAccount(Base):
    __tablename__ = "payout_accounts"

    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), unique=True)
    label: Mapped[str] = mapped_column(String(80))
    iban_last4: Mapped[str] = mapped_column(CHAR(4))


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
    payer_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    recipient_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
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
