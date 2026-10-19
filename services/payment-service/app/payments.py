"""Logique métier : paiements, remboursements, retraits, historique (CADRAGE §4.3)."""

import asyncio
import base64
import logging
import random
import uuid
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.orm.attributes import set_committed_value

from app.cards import CardCheck, CardError, check_card
from app.db import iso_utc, utcnow
from app.errors import api_error
from app.logging_setup import log_event
from app.metrics import AUTHORIZATION_SECONDS, DECLINES, TRANSACTIONS
from app.models import Client, PayoutAccount, Transaction
from app.recipients import Contact, parse_contact
from app.schemas import (
    AccountOut,
    CardIn,
    CardOut,
    PayIn,
    PaymentOut,
    PayoutAccountOut,
    PayoutOut,
    RefundOut,
    TransactionItem,
    TransactionList,
)
from app.security import fingerprint, new_reference

logger = logging.getLogger("payments")

# Le bénéficiaire ne voit que l'argent effectivement reçu, pas les tentatives refusées
VISIBLE_TO_RECIPIENT = ("authorized", "refunded", "completed")
UNKNOWN_RECIPIENT = "Destinataire inconnu"
PAYOUT_COUNTERPARTY = "Compte lié"


class SimulatedAuthorizer:
    """Réseau d'autorisation fictif : seule la latence est simulée, la carte fixe le résultat."""

    def __init__(self, min_ms: int, max_ms: int) -> None:
        self.min_ms = min_ms
        self.max_ms = max_ms

    async def authorize(self) -> None:
        await asyncio.sleep(random.uniform(self.min_ms, self.max_ms) / 1000)  # noqa: S311


# --- Outils communs ---------------------------------------------------------------


async def get_client(session: AsyncSession, client_id: str) -> Client:
    client = await session.get(Client, client_id)
    if client is None:
        raise api_error(401, "invalid_token", "Session invalide ou expirée.")
    return client


def check_amount(settings, amount_cents: int) -> None:
    if amount_cents > settings.max_amount_cents:
        raise api_error(
            422,
            "amount_too_large",
            f"Montant maximal : {settings.max_amount_cents // 100} € par opération.",
        )


def parse_contact_or_fail(raw: str) -> Contact:
    contact = parse_contact(raw)
    if contact is None:
        raise api_error(422, "invalid_recipient", "Email ou numéro de téléphone invalide.")
    return contact


def _reachable(found: Client | None, requester: Client) -> Client | None:
    # Les comptes de la sonde ne sont joignables que par la sonde (CADRAGE §4.4)
    if found is not None and found.is_probe and not requester.is_probe:
        return None
    return found


async def find_by_contact(session: AsyncSession, contact: Contact, requester: Client):
    column = Client.email if contact.kind == "email" else Client.phone
    found = (
        await session.execute(select(Client).where(column == contact.value))
    ).scalar_one_or_none()
    return _reachable(found, requester)


async def find_by_qr(session: AsyncSession, token: str, requester: Client) -> Client | None:
    found = (
        await session.execute(select(Client).where(Client.qr_token == token))
    ).scalar_one_or_none()
    return _reachable(found, requester)


def card_fingerprint(card: CardIn) -> dict[str, Any]:
    """Partie de l'empreinte liée à la carte : jamais le numéro complet ni le CVC."""
    digits = card.number.get_secret_value().replace(" ", "").replace("-", "")
    return {"card_last4": digits[-4:], "card_exp": f"{card.exp_month:02d}/{card.exp_year}"}


def validate_card(card: CardIn) -> CardCheck:
    try:
        return check_card(
            card.number.get_secret_value(),
            card.exp_month,
            card.exp_year,
            card.cvc.get_secret_value(),
            today=date.today(),
        )
    except CardError as exc:
        raise api_error(422, exc.code, exc.message) from None


async def find_replay(session: AsyncSession, model, owner_column, owner_id: str, key: str, fp: str):
    """Retourne l'objet déjà créé avec cette clé, ou None. 409 si la clé a servi à autre chose."""
    existing = (
        await session.execute(
            select(model).where(owner_column == owner_id, model.idempotency_key == key)
        )
    ).scalar_one_or_none()
    if existing is not None and existing.request_hash != fp:
        raise api_error(
            409,
            "idempotency_conflict",
            "Cette Idempotency-Key a déjà servi pour une autre requête.",
        )
    return existing


def payment_out(tx: Transaction) -> PaymentOut:
    return PaymentOut(
        reference=tx.reference,
        status=tx.status,
        decline_reason=tx.decline_reason,
        amount_cents=tx.amount_cents,
        currency=tx.currency,
        card=CardOut(brand=tx.card_brand, last4=tx.card_last4) if tx.card_last4 else None,
        created_at=iso_utc(tx.created_at),
    )


def _record(tx: Transaction) -> None:
    TRANSACTIONS.labels(type=tx.type, status=tx.status).inc()
    if tx.status == "declined" and tx.decline_reason:
        DECLINES.labels(reason=tx.decline_reason).inc()
    log_event(
        logger,
        f"{tx.type}_processed",
        reference=tx.reference,
        status=tx.status,
        decline_reason=tx.decline_reason,
        amount_cents=tx.amount_cents,
        payer_id=tx.payer_id,
        recipient_id=tx.recipient_id,
    )


async def _set_status(session: AsyncSession, tx: Transaction, status: str, reason: str | None):
    await session.execute(
        update(Transaction)
        .where(Transaction.id == tx.id, Transaction.status == "pending")
        .values(status=status, decline_reason=reason, updated_at=utcnow())
    )
    await session.commit()
    set_committed_value(tx, "status", status)
    set_committed_value(tx, "decline_reason", reason)


# --- Paiement -------------------------------------------------------------------------


async def charge(
    state,
    session: AsyncSession,
    payer: Client,
    recipient: Client | None,
    *,
    amount_cents: int,
    currency: str,
    description: str | None,
    card: CardCheck,
    key: str,
    fp: str,
    on_pending: Callable[[Transaction], Awaitable[bool]] | None = None,
) -> tuple[Transaction, bool]:
    """Crée le paiement, simule l'autorisation et crédite le bénéficiaire.

    Retourne (transaction, créée). `on_pending` permet de réserver une ressource (une demande
    d'argent) avant l'autorisation ; s'il retourne False, le paiement échoue.
    """
    tx = Transaction(
        id=str(uuid.uuid4()),
        reference=new_reference("tx"),
        type="payment",
        payer_id=payer.id,
        recipient_id=recipient.id if recipient else None,
        amount_cents=amount_cents,
        currency=currency,
        description=description,
        card_brand=card.brand,
        card_last4=card.last4,
        status="pending" if recipient else "declined",
        decline_reason=None if recipient else "recipient_not_found",
        idempotency_key=key,
        request_hash=fp,
    )
    session.add(tx)
    try:
        await session.commit()
    except IntegrityError:
        # Deux requêtes simultanées avec la même clé : la seconde rejoue la première
        await session.rollback()
        replay = await find_replay(session, Transaction, Transaction.payer_id, payer.id, key, fp)
        if replay is not None:
            return replay, False
        raise

    if tx.status == "pending":
        if on_pending is not None and not await on_pending(tx):
            await _set_status(session, tx, "failed", "request_not_pending")
            _record(tx)
            raise api_error(409, "request_not_pending", "Cette demande n'est plus à payer.")
        await authorize_and_settle(state, session, tx, card.decline_reason)

    _record(tx)
    return tx, True


async def authorize_and_settle(
    state, session: AsyncSession, tx: Transaction, decline_reason: str | None
) -> None:
    new_status = "authorized" if decline_reason is None else "declined"
    async with session.begin():
        # Le verrou garde une connexion du pool pendant l'autorisation : c'est ce qui fait
        # du pool la ressource critique du service (scénario SC-01).
        await session.execute(
            select(Transaction.id).where(Transaction.id == tx.id).with_for_update()
        )
        with AUTHORIZATION_SECONDS.time():
            await state.authorizer.authorize()
        result = await session.execute(
            update(Transaction)
            .where(Transaction.id == tx.id, Transaction.status == "pending")
            .values(status=new_status, decline_reason=decline_reason, updated_at=utcnow())
        )
        if result.rowcount != 1:
            raise api_error(409, "transaction_not_pending", "Ce paiement a déjà été clôturé.")
        if new_status == "authorized":
            await session.execute(
                update(Client)
                .where(Client.id == tx.recipient_id)
                .values(balance_cents=Client.balance_cents + tx.amount_cents)
            )
    set_committed_value(tx, "status", new_status)
    set_committed_value(tx, "decline_reason", decline_reason)


async def pay(
    state, session: AsyncSession, payer_id: str, body: PayIn, key: str
) -> tuple[Transaction, bool]:
    payer = await get_client(session, payer_id)
    check_amount(state.settings, body.amount_cents)

    contact = parse_contact_or_fail(body.recipient) if body.recipient else None
    target = contact.value if contact else f"qr:{body.recipient_qr}"
    fp = fingerprint(
        {
            "op": "pay",
            "recipient": target,
            "amount_cents": body.amount_cents,
            "currency": body.currency,
            "description": body.description,
            **card_fingerprint(body.card),
        }
    )
    replay = await find_replay(session, Transaction, Transaction.payer_id, payer.id, key, fp)
    if replay is not None:
        return replay, False

    card = validate_card(body.card)
    if contact:
        recipient = await find_by_contact(session, contact, payer)
    else:
        recipient = await find_by_qr(session, body.recipient_qr, payer)
    if recipient is not None and recipient.id == payer.id:
        raise api_error(422, "self_transfer", "Vous ne pouvez pas vous envoyer de l'argent.")

    return await charge(
        state,
        session,
        payer,
        recipient,
        amount_cents=body.amount_cents,
        currency=body.currency,
        description=body.description,
        card=card,
        key=key,
        fp=fp,
    )


# --- Remboursement --------------------------------------------------------------------


async def refund(
    session: AsyncSession, client_id: str, reference: str, key: str
) -> tuple[RefundOut, bool]:
    me = await get_client(session, client_id)
    original = (
        await session.execute(
            select(Transaction).where(
                Transaction.reference == reference, Transaction.type == "payment"
            )
        )
    ).scalar_one_or_none()
    visible = original is not None and (
        original.payer_id == me.id
        or (original.recipient_id == me.id and original.status in VISIBLE_TO_RECIPIENT)
    )
    if not visible:
        raise api_error(404, "transaction_not_found", "Transaction introuvable.")

    fp = fingerprint({"op": "refund", "of": reference})
    replay = await find_replay(session, Transaction, Transaction.payer_id, me.id, key, fp)
    if replay is not None:
        return _refund_out(replay, reference), False

    if original.recipient_id != me.id:
        raise api_error(403, "not_recipient", "Seul le bénéficiaire peut rembourser ce paiement.")
    if original.status == "refunded":
        raise api_error(409, "already_refunded", "Ce paiement a déjà été remboursé.")
    if original.status != "authorized":
        raise api_error(409, "not_refundable", "Seul un paiement autorisé peut être remboursé.")

    marked = await session.execute(
        update(Transaction)
        .where(Transaction.id == original.id, Transaction.status == "authorized")
        .values(status="refunded", updated_at=utcnow())
    )
    if marked.rowcount != 1:
        await session.rollback()
        raise api_error(409, "already_refunded", "Ce paiement a déjà été remboursé.")
    debited = await session.execute(
        update(Client)
        .where(Client.id == me.id, Client.balance_cents >= original.amount_cents)
        .values(balance_cents=Client.balance_cents - original.amount_cents)
    )
    if debited.rowcount != 1:
        await session.rollback()
        raise api_error(422, "insufficient_balance", "Solde insuffisant pour rembourser.")

    label = f"Remboursement · {original.description}" if original.description else "Remboursement"
    tx = Transaction(
        id=str(uuid.uuid4()),
        reference=new_reference("tx"),
        type="refund",
        payer_id=me.id,
        recipient_id=original.payer_id,
        parent_id=original.id,
        amount_cents=original.amount_cents,
        currency=original.currency,
        description=label[:140],
        card_brand=original.card_brand,
        card_last4=original.card_last4,
        status="completed",
        idempotency_key=key,
        request_hash=fp,
    )
    session.add(tx)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        replay = await find_replay(session, Transaction, Transaction.payer_id, me.id, key, fp)
        if replay is not None:
            return _refund_out(replay, reference), False
        raise api_error(409, "already_refunded", "Ce paiement a déjà été remboursé.") from None
    _record(tx)
    return _refund_out(tx, reference), True


def _refund_out(tx: Transaction, original_reference: str) -> RefundOut:
    return RefundOut(
        reference=tx.reference,
        status=tx.status,
        amount_cents=tx.amount_cents,
        refunded=original_reference,
    )


# --- Compte et retraits ---------------------------------------------------------------


async def _payout_account(session: AsyncSession, client_id: str) -> PayoutAccount | None:
    return (
        await session.execute(select(PayoutAccount).where(PayoutAccount.client_id == client_id))
    ).scalar_one_or_none()


async def account(session: AsyncSession, client_id: str) -> AccountOut:
    me = await get_client(session, client_id)
    linked = await _payout_account(session, me.id)
    return AccountOut(
        balance_cents=me.balance_cents,
        payout_account=PayoutAccountOut(label=linked.label, iban_last4=linked.iban_last4)
        if linked
        else None,
    )


async def payout(
    state, session: AsyncSession, client_id: str, amount_cents: int, key: str
) -> tuple[PayoutOut, bool]:
    me = await get_client(session, client_id)
    check_amount(state.settings, amount_cents)
    fp = fingerprint({"op": "payout", "amount_cents": amount_cents})
    replay = await find_replay(session, Transaction, Transaction.payer_id, me.id, key, fp)
    if replay is not None:
        return _payout_out(replay), False

    linked = await _payout_account(session, me.id)
    if linked is None:
        raise api_error(422, "no_payout_account", "Aucun compte lié pour recevoir le retrait.")
    debited = await session.execute(
        update(Client)
        .where(Client.id == me.id, Client.balance_cents >= amount_cents)
        .values(balance_cents=Client.balance_cents - amount_cents)
    )
    if debited.rowcount != 1:
        await session.rollback()
        raise api_error(422, "insufficient_balance", "Solde insuffisant.")

    tx = Transaction(
        id=str(uuid.uuid4()),
        reference=new_reference("tx"),
        type="payout",
        payer_id=me.id,
        amount_cents=amount_cents,
        currency="EUR",
        description=f"Retrait vers {linked.label} •••• {linked.iban_last4}",
        status="completed",
        idempotency_key=key,
        request_hash=fp,
    )
    session.add(tx)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        replay = await find_replay(session, Transaction, Transaction.payer_id, me.id, key, fp)
        if replay is not None:
            return _payout_out(replay), False
        raise
    _record(tx)
    return _payout_out(tx), True


def _payout_out(tx: Transaction) -> PayoutOut:
    return PayoutOut(
        reference=tx.reference,
        status=tx.status,
        amount_cents=tx.amount_cents,
        created_at=iso_utc(tx.created_at),
    )


# --- Historique -----------------------------------------------------------------------


def _visible_to(client_id: str, direction: str | None = None):
    sent = Transaction.payer_id == client_id
    received = and_(
        Transaction.recipient_id == client_id, Transaction.status.in_(VISIBLE_TO_RECIPIENT)
    )
    return {"sent": sent, "received": received, None: or_(sent, received)}[direction]


def _with_names(condition):
    payer = aliased(Client)
    recipient = aliased(Client)
    return (
        select(Transaction, payer.display_name, recipient.display_name)
        .outerjoin(payer, payer.id == Transaction.payer_id)
        .outerjoin(recipient, recipient.id == Transaction.recipient_id)
        .where(condition)
    )


def transaction_item(
    tx: Transaction, client_id: str, payer_name: str | None, recipient_name: str | None
) -> TransactionItem:
    direction = "sent" if tx.payer_id == client_id else "received"
    if tx.type == "payout":
        counterparty = PAYOUT_COUNTERPARTY
    elif direction == "sent":
        counterparty = recipient_name or UNKNOWN_RECIPIENT
    else:
        counterparty = payer_name or UNKNOWN_RECIPIENT
    return TransactionItem(
        reference=tx.reference,
        type=tx.type,
        direction=direction,
        counterparty=counterparty,
        description=tx.description,
        card_last4=tx.card_last4,
        amount_cents=tx.amount_cents,
        currency=tx.currency,
        status=tx.status,
        created_at=iso_utc(tx.created_at),
    )


def encode_cursor(tx: Transaction) -> str:
    raw = f"{tx.created_at.isoformat()}|{tx.id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        created_at, tx_id = raw.split("|", 1)
        return datetime.fromisoformat(created_at), tx_id
    except ValueError:
        raise api_error(422, "invalid_cursor", "Curseur de pagination invalide.") from None


async def list_transactions(
    session: AsyncSession,
    client_id: str,
    *,
    status: str | None,
    direction: str | None,
    limit: int,
    cursor: str | None,
) -> TransactionList:
    stmt = _with_names(_visible_to(client_id, direction))
    if status:
        stmt = stmt.where(Transaction.status == status)
    if cursor:
        created_at, tx_id = decode_cursor(cursor)
        stmt = stmt.where(
            or_(
                Transaction.created_at < created_at,
                and_(Transaction.created_at == created_at, Transaction.id < tx_id),
            )
        )
    stmt = stmt.order_by(Transaction.created_at.desc(), Transaction.id.desc()).limit(limit + 1)
    rows = (await session.execute(stmt)).all()
    items = [transaction_item(tx, client_id, p, r) for tx, p, r in rows[:limit]]
    next_cursor = encode_cursor(rows[limit - 1][0]) if len(rows) > limit else None
    return TransactionList(items=items, next_cursor=next_cursor)


async def get_transaction(session: AsyncSession, client_id: str, reference: str) -> TransactionItem:
    row = (
        await session.execute(
            _with_names(_visible_to(client_id)).where(Transaction.reference == reference)
        )
    ).first()
    if row is None:
        raise api_error(404, "transaction_not_found", "Transaction introuvable.")
    tx, payer_name, recipient_name = row
    return transaction_item(tx, client_id, payer_name, recipient_name)
