"""Demandes d'argent (« Demander ») et QR code de réception (CADRAGE §4.3)."""

import uuid
from datetime import timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.orm.attributes import set_committed_value

from app.db import iso_utc, utcnow
from app.errors import api_error
from app.metrics import REQUESTS
from app.models import Client, PaymentRequest, Transaction
from app.payments import (
    UNKNOWN_RECIPIENT,
    card_fingerprint,
    charge,
    check_amount,
    find_by_contact,
    find_replay,
    get_client,
    parse_contact_or_fail,
    validate_card,
)
from app.schemas import QrOut, RequestIn, RequestList, RequestOut, RequestPayIn
from app.security import fingerprint, new_qr_token, new_reference


def request_out(
    req: PaymentRequest, client_id: str, requester_name: str | None, payer_name: str | None
) -> RequestOut:
    incoming = req.payer_id == client_id
    return RequestOut(
        reference=req.reference,
        role="incoming" if incoming else "outgoing",
        counterparty=(requester_name if incoming else payer_name) or UNKNOWN_RECIPIENT,
        amount_cents=req.amount_cents,
        currency=req.currency,
        description=req.description,
        status=req.status,
        failure_reason=req.failure_reason,
        created_at=iso_utc(req.created_at),
        expires_at=iso_utc(req.expires_at),
    )


async def expire_requests(session: AsyncSession) -> int:
    result = await session.execute(
        update(PaymentRequest)
        .where(PaymentRequest.status == "pending", PaymentRequest.expires_at <= utcnow())
        .values(status="expired", updated_at=utcnow())
    )
    return result.rowcount


async def create_request(
    state, session: AsyncSession, client_id: str, body: RequestIn, key: str
) -> tuple[RequestOut, bool]:
    me = await get_client(session, client_id)
    check_amount(state.settings, body.amount_cents)
    contact = parse_contact_or_fail(body.payer)
    fp = fingerprint(
        {
            "op": "request",
            "payer": contact.value,
            "amount_cents": body.amount_cents,
            "description": body.description,
        }
    )

    async def names(req: PaymentRequest) -> str | None:
        payer = await session.get(Client, req.payer_id) if req.payer_id else None
        return payer.display_name if payer else None

    replay = await find_replay(session, PaymentRequest, PaymentRequest.requester_id, me.id, key, fp)
    if replay is not None:
        return request_out(replay, me.id, me.display_name, await names(replay)), False

    payer = await find_by_contact(session, contact, me)
    if payer is not None and payer.id == me.id:
        raise api_error(422, "self_request", "Vous ne pouvez pas vous demander de l'argent.")

    await expire_requests(session)
    pending = await session.scalar(
        select(func.count())
        .select_from(PaymentRequest)
        .where(PaymentRequest.requester_id == me.id, PaymentRequest.status == "pending")
    )
    if pending >= state.settings.max_pending_requests:
        raise api_error(
            422, "too_many_pending_requests", "Trop de demandes en attente. Annulez-en une."
        )

    now = utcnow()
    req = PaymentRequest(
        id=str(uuid.uuid4()),
        reference=new_reference("rq"),
        requester_id=me.id,
        payer_id=payer.id if payer else None,
        amount_cents=body.amount_cents,
        currency="EUR",
        description=body.description,
        # Payeur introuvable : même réponse neutre que pour un paiement (anti-énumération)
        status="pending" if payer else "failed",
        failure_reason=None if payer else "recipient_not_found",
        idempotency_key=key,
        request_hash=fp,
        created_at=now,
        expires_at=now + timedelta(days=state.settings.request_ttl_days),
    )
    session.add(req)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        replay = await find_replay(
            session, PaymentRequest, PaymentRequest.requester_id, me.id, key, fp
        )
        if replay is not None:
            return request_out(replay, me.id, me.display_name, await names(replay)), False
        raise
    REQUESTS.labels(status=req.status).inc()
    return request_out(req, me.id, me.display_name, payer.display_name if payer else None), True


async def list_requests(
    session: AsyncSession, client_id: str, *, role: str | None, status: str | None
) -> RequestList:
    await expire_requests(session)
    await session.commit()
    incoming = (PaymentRequest.payer_id == client_id) & (PaymentRequest.status != "failed")
    outgoing = PaymentRequest.requester_id == client_id
    condition = {"incoming": incoming, "outgoing": outgoing, None: or_(incoming, outgoing)}[role]
    requester = aliased(Client)
    payer = aliased(Client)
    stmt = (
        select(PaymentRequest, requester.display_name, payer.display_name)
        .join(requester, requester.id == PaymentRequest.requester_id)
        .outerjoin(payer, payer.id == PaymentRequest.payer_id)
        .where(condition)
    )
    if status:
        stmt = stmt.where(PaymentRequest.status == status)
    stmt = stmt.order_by(PaymentRequest.created_at.desc()).limit(50)
    rows = (await session.execute(stmt)).all()
    return RequestList(items=[request_out(req, client_id, r, p) for req, r, p in rows])


async def _load_request(session: AsyncSession, client_id: str, reference: str) -> PaymentRequest:
    req = (
        await session.execute(select(PaymentRequest).where(PaymentRequest.reference == reference))
    ).scalar_one_or_none()
    if req is None or client_id not in (req.payer_id, req.requester_id):
        raise api_error(404, "request_not_found", "Demande introuvable.")
    return req


async def _ensure_pending(session: AsyncSession, req: PaymentRequest) -> None:
    if req.status == "pending" and req.expires_at <= utcnow():
        await expire_requests(session)
        await session.commit()
        set_committed_value(req, "status", "expired")
    if req.status != "pending":
        raise api_error(409, "request_not_pending", "Cette demande n'est plus à payer.")


async def _out(session: AsyncSession, req: PaymentRequest, client_id: str) -> RequestOut:
    requester = await session.get(Client, req.requester_id)
    payer = await session.get(Client, req.payer_id) if req.payer_id else None
    return request_out(
        req,
        client_id,
        requester.display_name if requester else None,
        payer.display_name if payer else None,
    )


async def pay_request(
    state, session: AsyncSession, client_id: str, reference: str, body: RequestPayIn, key: str
) -> tuple[Transaction, bool]:
    me = await get_client(session, client_id)
    req = await _load_request(session, me.id, reference)
    if req.requester_id == me.id:
        raise api_error(403, "not_payer", "Vous ne pouvez pas payer votre propre demande.")

    fp = fingerprint({"op": "request_pay", "request": reference, **card_fingerprint(body.card)})
    replay = await find_replay(session, Transaction, Transaction.payer_id, me.id, key, fp)
    if replay is not None:
        return replay, False

    await _ensure_pending(session, req)
    card = validate_card(body.card)
    requester = await session.get(Client, req.requester_id)

    async def claim(tx: Transaction) -> bool:
        # Réserve la demande pour ce paiement : empêche de la payer deux fois
        claimed = await session.execute(
            update(PaymentRequest)
            .where(
                PaymentRequest.id == req.id,
                PaymentRequest.status == "pending",
                PaymentRequest.transaction_id.is_(None),
            )
            .values(transaction_id=tx.id, updated_at=utcnow())
        )
        await session.commit()
        return claimed.rowcount == 1

    tx, created = await charge(
        state,
        session,
        me,
        requester,
        amount_cents=req.amount_cents,
        currency=req.currency,
        description=req.description,
        card=card,
        key=key,
        fp=fp,
        on_pending=claim,
    )
    if created:
        if tx.status == "authorized":
            values = {"status": "paid"}
        else:
            values = {"transaction_id": None}  # carte refusée : la demande reste à payer
        await session.execute(
            update(PaymentRequest)
            .where(PaymentRequest.id == req.id, PaymentRequest.transaction_id == tx.id)
            .values(updated_at=utcnow(), **values)
        )
        await session.commit()
        if tx.status == "authorized":
            REQUESTS.labels(status="paid").inc()
    return tx, created


async def _close_request(
    session: AsyncSession, client_id: str, reference: str, *, by: str, new_status: str
) -> RequestOut:
    req = await _load_request(session, client_id, reference)
    owner = req.payer_id if by == "payer" else req.requester_id
    if owner != client_id:
        if by == "payer":
            raise api_error(403, "not_payer", "Seul le payeur demandé peut refuser.")
        raise api_error(403, "not_requester", "Seul le demandeur peut annuler.")
    await _ensure_pending(session, req)
    result = await session.execute(
        update(PaymentRequest)
        .where(
            PaymentRequest.id == req.id,
            PaymentRequest.status == "pending",
            PaymentRequest.transaction_id.is_(None),
        )
        .values(status=new_status, updated_at=utcnow())
    )
    await session.commit()
    if result.rowcount != 1:
        raise api_error(409, "request_not_pending", "Cette demande n'est plus à payer.")
    set_committed_value(req, "status", new_status)
    REQUESTS.labels(status=new_status).inc()
    return await _out(session, req, client_id)


async def decline_request(session: AsyncSession, client_id: str, reference: str) -> RequestOut:
    return await _close_request(session, client_id, reference, by="payer", new_status="declined")


async def cancel_request(session: AsyncSession, client_id: str, reference: str) -> RequestOut:
    return await _close_request(
        session, client_id, reference, by="requester", new_status="cancelled"
    )


# --- QR code --------------------------------------------------------------------------


def _qr_out(client: Client) -> QrOut:
    return QrOut(
        qr_token=client.qr_token,
        payload=f"orbe://pay?to={client.qr_token}",
        display_name=client.display_name,
    )


async def get_qr(session: AsyncSession, client_id: str) -> QrOut:
    me = await get_client(session, client_id)
    if me.qr_token is None:
        await session.execute(
            update(Client)
            .where(Client.id == me.id, Client.qr_token.is_(None))
            .values(qr_token=new_qr_token())
        )
        await session.commit()
        await session.refresh(me)
    return _qr_out(me)


async def rotate_qr(session: AsyncSession, client_id: str) -> QrOut:
    me = await get_client(session, client_id)
    await session.execute(update(Client).where(Client.id == me.id).values(qr_token=new_qr_token()))
    await session.commit()
    await session.refresh(me)
    return _qr_out(me)
