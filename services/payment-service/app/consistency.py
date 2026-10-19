"""Cohérence des données : réconciliation et invariant des soldes (CADRAGE §4.3 et §7.5)."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import utcnow
from app.logging_setup import log_event
from app.metrics import RECONCILED
from app.models import Client, PaymentRequest, Transaction
from app.payment_requests import expire_requests

logger = logging.getLogger("consistency")


async def reconcile(sessionmaker: async_sessionmaker, older_than_seconds: int) -> int:
    """Passe en « failed » les paiements restés « pending » (instance tombée en cours de route).

    Libère aussi les demandes d'argent réservées par ces paiements et expire les demandes
    échues. Retourne le nombre de paiements réconciliés.
    """
    cutoff = utcnow() - timedelta(seconds=older_than_seconds)
    async with sessionmaker() as session:
        result = await session.execute(
            update(Transaction)
            .where(Transaction.status == "pending", Transaction.created_at < cutoff)
            .values(status="failed", decline_reason="recovery", updated_at=utcnow())
        )
        failed = select(Transaction.id).where(Transaction.status.in_(("failed", "declined")))
        await session.execute(
            update(PaymentRequest)
            .where(PaymentRequest.status == "pending", PaymentRequest.transaction_id.in_(failed))
            .values(transaction_id=None, updated_at=utcnow())
        )
        await expire_requests(session)
        await session.commit()
    if result.rowcount:
        RECONCILED.inc(result.rowcount)
        log_event(logger, "pending_reconciled", count=result.rowcount)
    return result.rowcount


async def reconcile_forever(sessionmaker, older_than_seconds: int, interval: float) -> None:
    """Tâche de fond : une réconciliation au démarrage, puis à intervalle régulier."""
    while True:
        try:
            await reconcile(sessionmaker, older_than_seconds)
        except Exception:
            # Base indisponible : on réessaiera au prochain tour, sans faire tomber le service
            logger.warning("reconcile_failed", exc_info=True)
        await asyncio.sleep(interval)


@dataclass(frozen=True)
class BalanceViolation:
    client_id: str
    balance_cents: int
    expected_cents: int


def _sum(*conditions):
    return (
        select(func.coalesce(func.sum(Transaction.amount_cents), 0))
        .where(*conditions)
        .scalar_subquery()
    )


async def balance_violations(session: AsyncSession) -> list[BalanceViolation]:
    """Invariant : solde = paiements reçus (autorisés ou remboursés) − remboursements − retraits.

    Requête de référence pour le contrôle de cohérence du moteur de remédiation.
    """
    received = _sum(
        Transaction.type == "payment",
        Transaction.recipient_id == Client.id,
        Transaction.status.in_(("authorized", "refunded")),
    )
    refunded = _sum(
        Transaction.type == "refund",
        Transaction.payer_id == Client.id,
        Transaction.status == "completed",
    )
    paid_out = _sum(
        Transaction.type == "payout",
        Transaction.payer_id == Client.id,
        Transaction.status == "completed",
    )
    expected = (received - refunded - paid_out).label("expected")
    rows = await session.execute(
        select(Client.id, Client.balance_cents, expected).where(Client.balance_cents != expected)
    )
    return [BalanceViolation(client_id, balance, int(exp)) for client_id, balance, exp in rows]
