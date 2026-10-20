"""Comptabilité en partie double (docs/mcd.md §5).

Toute opération autorisée ou effectuée passe exactement deux écritures de même montant :
un débit et un crédit. Les comptes de contrepartie représentent l'extérieur d'Orbe.

| Opération          | Débit                       | Crédit                      |
|--------------------|-----------------------------|-----------------------------|
| Paiement autorisé  | contrepartie card_settlement | compte du bénéficiaire     |
| Remboursement      | compte du bénéficiaire      | contrepartie card_settlement |
| Retrait            | compte du client            | contrepartie payouts        |
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LedgerAccount, LedgerEntry

CARD_SETTLEMENT = "card_settlement"
PAYOUTS = "payouts"


class InsufficientFunds(Exception):
    """Le compte client à débiter n'a pas un solde suffisant."""


async def find_client_account(session: AsyncSession, client_id: str) -> LedgerAccount | None:
    return (
        await session.execute(select(LedgerAccount).where(LedgerAccount.client_id == client_id))
    ).scalar_one_or_none()


async def ensure_client_account(session: AsyncSession, client_id: str) -> LedgerAccount:
    """Compte Orbe du client, créé à la première réception d'argent.

    Valide sa propre transaction (à appeler avant le traitement de l'opération).
    """
    account = await find_client_account(session, client_id)
    if account is not None:
        await session.commit()  # clôt la transaction de lecture
        return account
    session.add(
        LedgerAccount(id=str(uuid.uuid4()), type="client", label="Compte Orbe", client_id=client_id)
    )
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()  # créé en parallèle par une autre requête
    account = await find_client_account(session, client_id)
    await session.commit()
    return account


async def counterpart(session: AsyncSession, code: str) -> LedgerAccount:
    account = (
        await session.execute(select(LedgerAccount).where(LedgerAccount.code == code))
    ).scalar_one_or_none()
    if account is None:
        raise RuntimeError(f"Compte de contrepartie {code} absent (voir 01-schema.sql)")
    return account


async def post(
    session: AsyncSession,
    transaction_id: str,
    *,
    debit: LedgerAccount,
    credit: LedgerAccount,
    amount_cents: int,
) -> None:
    """Passe les deux écritures et met à jour les soldes dans la transaction SQL en cours.

    Le débit d'un compte client est conditionné à son solde (mise à jour atomique) ;
    les comptes de contrepartie peuvent devenir négatifs.
    """
    conditions = [LedgerAccount.id == debit.id]
    if debit.type == "client":
        conditions.append(LedgerAccount.balance_cents >= amount_cents)
    debited = await session.execute(
        update(LedgerAccount)
        .where(*conditions)
        .values(balance_cents=LedgerAccount.balance_cents - amount_cents)
    )
    if debited.rowcount != 1:
        raise InsufficientFunds
    await session.execute(
        update(LedgerAccount)
        .where(LedgerAccount.id == credit.id)
        .values(balance_cents=LedgerAccount.balance_cents + amount_cents)
    )
    session.add_all(
        [
            LedgerEntry(
                transaction_id=transaction_id,
                account_id=debit.id,
                direction="debit",
                amount_cents=amount_cents,
            ),
            LedgerEntry(
                transaction_id=transaction_id,
                account_id=credit.id,
                direction="credit",
                amount_cents=amount_cents,
            ),
        ]
    )
