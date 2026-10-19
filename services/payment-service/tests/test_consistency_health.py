import uuid
from datetime import timedelta

from conftest import OK_CARD
from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine

from app.consistency import balance_violations, reconcile
from app.db import utcnow
from app.models import Client, PaymentRequest, Transaction


def test_balance_invariant_holds_after_every_kind_of_operation(add_client, pay, client, auth, db):
    camille, lea, hugo = add_client(), add_client(), add_client()
    pay(camille, lea, amount=1250)
    refundable = pay(hugo, lea, amount=2500).json()["reference"]
    pay(camille, lea, card={**OK_CARD, "number": "4000 0000 0000 0002"})
    client.post(f"/transactions/{refundable}/refund", headers=auth(lea))
    client.post("/payouts", json={"amount_cents": 250}, headers=auth(lea))

    assert db.run(balance_violations) == []
    assert db.get(Client, lea.id).balance_cents == 1000


def test_balance_invariant_detects_tampering(add_client, pay, db):
    camille, lea = add_client(), add_client()
    pay(camille, lea, amount=1250)

    async def tamper(session):
        await session.execute(update(Client).where(Client.id == lea.id).values(balance_cents=9999))

    db.run(tamper)
    violations = db.run(balance_violations)

    assert [(v.client_id, v.balance_cents, v.expected_cents) for v in violations] == [
        (lea.id, 9999, 1250)
    ]


def test_reconciliation_fails_stale_pending_payments_only(app, add_client, db):
    camille, lea = add_client(), add_client()

    def pending(age_seconds):
        return Transaction(
            id=str(uuid.uuid4()),
            reference=f"tx_{uuid.uuid4().hex[:8]}",
            type="payment",
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
