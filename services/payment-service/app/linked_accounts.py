"""Comptes liés (comptes bancaires fictifs qui reçoivent les retraits), RG-15."""

import re
import uuid

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import utcnow
from app.errors import api_error
from app.models import PayoutAccount
from app.payments import payout_account_out, payout_accounts_of
from app.schemas import PayoutAccountIn, PayoutAccountOut

_IBAN = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")


def iban_last4(raw: str) -> str:
    """Vérifie le format et la clé (mod 97) d'un IBAN ; ne conserve que ses 4 derniers caractères.

    L'IBAN complet n'est ni stocké ni journalisé.
    """
    iban = raw.replace(" ", "").upper()
    if not _IBAN.fullmatch(iban):
        raise api_error(422, "invalid_iban", "IBAN invalide.")
    digits = "".join(str(int(c, 36)) for c in iban[4:] + iban[:4])
    if int(digits) % 97 != 1:
        raise api_error(422, "invalid_iban", "IBAN invalide (clé de contrôle).")
    return iban[-4:]


async def _owned(session: AsyncSession, client_id: str, account_id: str) -> PayoutAccount:
    account = await session.get(PayoutAccount, account_id)
    if account is None or account.client_id != client_id:
        raise api_error(404, "payout_account_not_found", "Compte lié introuvable.")
    return account


async def _make_default(session: AsyncSession, client_id: str, account_id: str) -> None:
    # Une seule requête : exactement un compte par défaut à tout instant
    await session.execute(
        update(PayoutAccount)
        .where(PayoutAccount.client_id == client_id)
        .values(is_default=case((PayoutAccount.id == account_id, True), else_=False))
    )


async def list_accounts(session: AsyncSession, client_id: str) -> list[PayoutAccountOut]:
    return [payout_account_out(a) for a in await payout_accounts_of(session, client_id)]


async def add_account(
    state, session: AsyncSession, client_id: str, body: PayoutAccountIn
) -> PayoutAccountOut:
    last4 = iban_last4(body.iban)
    count = await session.scalar(
        select(func.count()).select_from(PayoutAccount).where(PayoutAccount.client_id == client_id)
    )
    if count >= state.settings.max_payout_accounts:
        raise api_error(
            422,
            "too_many_payout_accounts",
            f"{state.settings.max_payout_accounts} comptes liés au maximum.",
        )
    account = PayoutAccount(
        id=str(uuid.uuid4()),
        client_id=client_id,
        label=body.label,
        iban_last4=last4,
        is_default=count == 0,  # le premier compte devient le compte par défaut
        created_at=utcnow(),
    )
    session.add(account)
    await session.commit()
    if body.make_default and count:
        await _make_default(session, client_id, account.id)
        await session.commit()
        await session.refresh(account)
    return payout_account_out(account)


async def set_default(session: AsyncSession, client_id: str, account_id: str) -> PayoutAccountOut:
    account = await _owned(session, client_id, account_id)
    await _make_default(session, client_id, account.id)
    await session.commit()
    await session.refresh(account)
    return payout_account_out(account)


async def delete_account(session: AsyncSession, client_id: str, account_id: str) -> None:
    account = await _owned(session, client_id, account_id)
    was_default = account.is_default
    await session.delete(account)
    await session.flush()
    if was_default:
        remaining = await payout_accounts_of(session, client_id)
        if remaining:
            newest = max(remaining, key=lambda a: a.created_at)
            await _make_default(session, client_id, newest.id)
    await session.commit()
