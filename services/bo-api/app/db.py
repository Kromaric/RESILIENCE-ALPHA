"""Accès en lecture seule à la base (compte bo_ro, voir infra/mariadb/init/02-users.sh).

Les tables ne sont décrites qu'avec les colonnes que bo_ro a le droit de lire : une requête
sur une autre colonne échouerait en base. Les clients ne sont lisibles qu'à travers la vue
`bo_clients`, dont l'email et le téléphone sont déjà masqués par MariaDB.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.config import Settings

metadata = MetaData()

bo_clients = Table(
    "bo_clients",
    metadata,
    Column("id", CHAR(36), primary_key=True),
    Column("display_name", String(80)),
    Column("email_masked", String(260)),
    Column("phone_masked", String(32)),
    Column("is_probe", Boolean),
    Column("failed_logins", Integer),
    Column("locked_until", DateTime, nullable=True),
    Column("face_enrolled", Boolean),
    Column("created_at", DateTime),
)

transactions = Table(
    "transactions",
    metadata,
    Column("id", CHAR(36), primary_key=True),
    Column("reference", CHAR(11)),
    Column("type", String(16)),  # payment | refund | payout
    Column("payer_id", CHAR(36)),
    Column("recipient_id", CHAR(36), nullable=True),
    Column("parent_id", CHAR(36), nullable=True),
    Column("payout_account_id", CHAR(36), nullable=True),
    Column("amount_cents", Integer),
    Column("currency", CHAR(3)),
    Column("description", String(140), nullable=True),
    Column("card_brand", String(16), nullable=True),
    Column("card_last4", CHAR(4), nullable=True),
    Column("status", String(16)),
    Column("decline_reason", String(32), nullable=True),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)

ledger_accounts = Table(
    "ledger_accounts",
    metadata,
    Column("id", CHAR(36), primary_key=True),
    Column("type", String(16)),  # client | counterpart
    Column("code", String(32), nullable=True),
    Column("label", String(80)),
    Column("balance_cents", BigInteger),
    Column("client_id", CHAR(36), nullable=True),
)

ledger_entries = Table(
    "ledger_entries",
    metadata,
    # INTEGER sous SQLite (tests) : seul type auto-incrémenté
    Column("id", BigInteger().with_variant(Integer, "sqlite"), primary_key=True),
    Column("transaction_id", CHAR(36)),
    Column("account_id", CHAR(36)),
    Column("direction", String(8)),  # debit | credit
    Column("amount_cents", Integer),
    Column("created_at", DateTime),
)

payment_requests = Table(
    "payment_requests",
    metadata,
    Column("id", CHAR(36), primary_key=True),
    Column("reference", CHAR(11)),
    Column("requester_id", CHAR(36)),
    Column("payer_id", CHAR(36), nullable=True),
    Column("transaction_id", CHAR(36), nullable=True),
    Column("amount_cents", Integer),
    Column("currency", CHAR(3)),
    Column("description", String(140), nullable=True),
    Column("status", String(16)),
    Column("failure_reason", String(32), nullable=True),
    Column("created_at", DateTime),
    Column("expires_at", DateTime),
    Column("updated_at", DateTime),
)

payout_accounts = Table(
    "payout_accounts",
    metadata,
    Column("id", CHAR(36), primary_key=True),
    Column("client_id", CHAR(36)),
    Column("label", String(80)),
    Column("iban_last4", CHAR(4)),
    Column("is_default", Boolean),
    Column("created_at", DateTime),
)

sessions = Table(
    "sessions",
    metadata,
    Column("id", CHAR(36), primary_key=True),
    Column("client_id", CHAR(36)),
    Column("status", String(16)),
    Column("opened_at", DateTime),
    Column("expires_at", DateTime),
)


def utcnow() -> datetime:
    """Date UTC sans fuseau, cohérente avec les colonnes DATETIME de MariaDB."""
    return datetime.now(UTC).replace(tzinfo=None)


def iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def make_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.sqlalchemy_url(),
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=0,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=1800,
    )


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session
