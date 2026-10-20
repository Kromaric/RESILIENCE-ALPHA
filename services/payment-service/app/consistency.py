"""Cohérence des données : réconciliation et invariant des soldes (CADRAGE §4.3 et §7.5)."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import utcnow
from app.logging_setup import log_event
from app.metrics import RECONCILED
from app.models import LedgerAccount, LedgerEntry, PaymentRequest, Transaction
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
class LedgerViolation:
    kind: str  # unbalanced_operation | entry_count | balance_mismatch | negative_client_balance
    subject: str  # identifiant de l'opération ou du compte
    detail: str


# Statuts d'une opération qui doivent avoir passé exactement deux écritures
SETTLED = ("authorized", "refunded", "completed")


async def ledger_violations(session: AsyncSession) -> list[LedgerViolation]:
    """Contrôles de cohérence de la comptabilité en partie double (CADRAGE §4.3, §7.5).

    1. Pour chaque opération : Σ débits = Σ crédits.
    2. Opération réglée → exactement 2 écritures ; refusée, échouée ou en attente → aucune.
    3. Pour chaque compte : solde = Σ crédits − Σ débits.
    4. Aucun compte client en solde négatif.

    Requêtes de référence pour le contrôle de cohérence du moteur de remédiation.
    """
    violations: list[LedgerViolation] = []
    signed = case(
        (LedgerEntry.direction == "credit", LedgerEntry.amount_cents),
        else_=-LedgerEntry.amount_cents,
    )

    unbalanced = await session.execute(
        select(LedgerEntry.transaction_id, func.sum(signed))
        .group_by(LedgerEntry.transaction_id)
        .having(func.sum(signed) != 0)
    )
    violations += [
        LedgerViolation("unbalanced_operation", tx_id, f"écart {gap}") for tx_id, gap in unbalanced
    ]

    counts = (
        select(LedgerEntry.transaction_id, func.count().label("n"))
        .group_by(LedgerEntry.transaction_id)
        .subquery()
    )
    entry_count = func.coalesce(counts.c.n, 0)
    wrong_count = await session.execute(
        select(Transaction.id, Transaction.status, entry_count)
        .outerjoin(counts, counts.c.transaction_id == Transaction.id)
        .where(
            or_(
                and_(Transaction.status.in_(SETTLED), entry_count != 2),
                and_(Transaction.status.not_in(SETTLED), entry_count != 0),
            )
        )
    )
    violations += [
        LedgerViolation("entry_count", tx_id, f"statut {status}, {n} écriture(s)")
        for tx_id, status, n in wrong_count
    ]

    totals = (
        select(LedgerEntry.account_id, func.sum(signed).label("total"))
        .group_by(LedgerEntry.account_id)
        .subquery()
    )
    expected = func.coalesce(totals.c.total, 0)
    mismatched = await session.execute(
        select(LedgerAccount.id, LedgerAccount.balance_cents, expected)
        .outerjoin(totals, totals.c.account_id == LedgerAccount.id)
        .where(LedgerAccount.balance_cents != expected)
    )
    violations += [
        LedgerViolation("balance_mismatch", account_id, f"solde {balance}, écritures {int(total)}")
        for account_id, balance, total in mismatched
    ]

    negative = await session.execute(
        select(LedgerAccount.id, LedgerAccount.balance_cents).where(
            LedgerAccount.type == "client", LedgerAccount.balance_cents < 0
        )
    )
    violations += [
        LedgerViolation("negative_client_balance", account_id, f"solde {balance}")
        for account_id, balance in negative
    ]
    return violations
