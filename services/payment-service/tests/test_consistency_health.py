import uuid
from datetime import timedelta

from conftest import CARD_ACCOUNT, OK_CARD, PAYOUT_ACCOUNT, _open_session
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine

from app.consistency import ledger_violations, reconcile
from app.db import utcnow
from app.models import LedgerAccount, LedgerEntry, PaymentRequest, Transaction


def entries_of(db, reference):
    async def _entries(session):
        rows = await session.execute(
            select(LedgerEntry.direction, LedgerEntry.account_id, LedgerEntry.amount_cents)
            .join(Transaction, Transaction.id == LedgerEntry.transaction_id)
            .where(Transaction.reference == reference)
            .order_by(LedgerEntry.direction)
        )
        return [tuple(r) for r in rows]

    return db.run(_entries)


def account_id(db, client_row):
    async def _id(session):
        return await session.scalar(
            select(LedgerAccount.id).where(LedgerAccount.client_id == client_row.id)
        )

    return db.run(_id)


# --- Écritures --------------------------------------------------------------------


def test_an_authorized_payment_posts_two_balanced_entries(add_client, pay, db):
    camille, lea = add_client(), add_client()

    reference = pay(camille, lea, amount=1250).json()["reference"]

    assert entries_of(db, reference) == [
        ("credit", account_id(db, lea), 1250),
        ("debit", CARD_ACCOUNT, 1250),
    ]


def test_a_declined_payment_posts_no_entry(add_client, pay, db):
    camille, lea = add_client(), add_client()

    reference = pay(camille, lea, card={**OK_CARD, "number": "4000 0000 0000 0002"}).json()[
        "reference"
    ]

    assert entries_of(db, reference) == []


def test_refund_and_payout_entries(add_client, pay, client, auth, db):
    camille, lea = add_client(), add_client()
    paid = pay(camille, lea, amount=2000).json()["reference"]

    refund = client.post(f"/transactions/{paid}/refund", headers=auth(lea)).json()["reference"]
    pay(camille, lea, amount=500)
    payout = client.post("/payouts", json={"amount_cents": 300}, headers=auth(lea)).json()

    lea_account = account_id(db, lea)
    assert entries_of(db, refund) == [("credit", CARD_ACCOUNT, 2000), ("debit", lea_account, 2000)]
    assert entries_of(db, payout["reference"]) == [
        ("credit", PAYOUT_ACCOUNT, 300),
        ("debit", lea_account, 300),
    ]


def test_ledger_is_consistent_after_every_kind_of_operation(add_client, pay, client, auth, db):
    camille, lea, hugo = add_client(), add_client(), add_client()
    pay(camille, lea, amount=1250)
    refundable = pay(hugo, lea, amount=2500).json()["reference"]
    pay(camille, lea, card={**OK_CARD, "number": "4000 0000 0000 0002"})
    client.post(f"/transactions/{refundable}/refund", headers=auth(lea))
    client.post("/payouts", json={"amount_cents": 250}, headers=auth(lea))

    assert db.run(ledger_violations) == []
    assert db.balance(lea) == 1000
    assert db.get(LedgerAccount, CARD_ACCOUNT).balance_cents == -1250
    assert db.get(LedgerAccount, PAYOUT_ACCOUNT).balance_cents == 250


def test_ledger_checks_detect_tampering(add_client, pay, db):
    camille, lea = add_client(), add_client()
    reference = pay(camille, lea, amount=1250).json()["reference"]
    lea_account = account_id(db, lea)

    async def tamper(session):
        await session.execute(
            update(LedgerAccount).where(LedgerAccount.id == lea_account).values(balance_cents=9999)
        )
        tx_id = await session.scalar(
            select(Transaction.id).where(Transaction.reference == reference)
        )
        session.add(
            LedgerEntry(
                transaction_id=tx_id, account_id=lea_account, direction="credit", amount_cents=1
            )
        )

    db.run(tamper)
    kinds = {v.kind for v in db.run(ledger_violations)}

    assert kinds == {"unbalanced_operation", "entry_count", "balance_mismatch"}


# --- Réconciliation ---------------------------------------------------------------


def test_reconciliation_fails_stale_pending_payments_only(app, add_client, db):
    camille, lea = add_client(), add_client()
    session = _open_session(db, camille)

    def pending(age_seconds):
        return Transaction(
            id=str(uuid.uuid4()),
            reference=f"tx_{uuid.uuid4().hex[:8]}",
            type="payment",
            session_id=session.id,
            payer_id=camille.id,
            recipient_id=lea.id,
            amount_cents=100,
            currency="EUR",
            status="pending",
            idempotency_key=str(uuid.uuid4()),
            request_hash="0" * 64,
            created_at=utcnow() - timedelta(seconds=age_seconds),
        )

    stale, fresh = pending(60), pending(1)
    request = PaymentRequest(
        id=str(uuid.uuid4()),
        reference="rq_00000001",
        requester_id=lea.id,
        payer_id=camille.id,
        transaction_id=stale.id,
        amount_cents=100,
        status="pending",
        idempotency_key=str(uuid.uuid4()),
        request_hash="0" * 64,
        expires_at=utcnow() + timedelta(days=1),
    )
    db.add(stale, fresh)
    db.add(request)

    count = db.call(reconcile, app.state.sessionmaker, 30)

    assert count == 1
    assert db.get(Transaction, stale.id).status == "failed"
    assert db.get(Transaction, stale.id).decline_reason == "recovery"
    assert db.get(Transaction, fresh.id).status == "pending"
    assert db.get(PaymentRequest, request.id).transaction_id is None


# --- Santé et métriques -----------------------------------------------------------


def test_live(client):
    assert client.get("/health/live").json() == {"status": "ok"}


def test_ready_when_the_database_answers(client):
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "up", "pool": "ok"}


def test_not_ready_when_the_database_is_unreachable(app, client):
    healthy = app.state.engine
    app.state.engine = create_async_engine("sqlite+aiosqlite:////dossier-inexistant/orbe.db")
    try:
        response = client.get("/health/ready")
    finally:
        app.state.engine = healthy

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "down"


def test_metrics_expose_business_and_pool_metrics(add_client, pay, client):
    camille, lea = add_client(), add_client()
    pay(camille, lea)
    pay(camille, lea, card={**OK_CARD, "number": "4000 0000 0000 0069"})

    body = client.get("/metrics").text

    assert 'payment_transactions_total{status="authorized",type="payment"}' in body
    assert 'payment_declines_total{reason="card_expired"}' in body
    assert "payment_db_pool_in_use" in body
    assert "payment_authorization_seconds_bucket" in body
