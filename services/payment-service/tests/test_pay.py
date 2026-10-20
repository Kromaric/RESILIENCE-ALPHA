import re
import uuid

import pytest
from conftest import OK_CARD
from sqlalchemy import exc as sa_exc

from app.models import Transaction


def stored(db, reference):
    async def _find(session):
        from sqlalchemy import select

        return (
            await session.execute(select(Transaction).where(Transaction.reference == reference))
        ).scalar_one()

    return db.run(_find)


def test_authorized_payment_credits_the_recipient(add_client, pay, db):
    payer, recipient = add_client("Camille Test"), add_client("Léa Martin")

    response = pay(payer, recipient, amount=1250, description="Ciné")

    assert response.status_code == 201
    body = response.json()
    assert re.fullmatch(r"tx_[0-9a-f]{8}", body["reference"])
    assert body["status"] == "authorized"
    assert body["decline_reason"] is None
    assert body["card"] == {"brand": "visa", "last4": "4242"}
    assert db.balance(recipient) == 1250
    assert db.balance(payer) == 0


def test_full_card_number_is_never_stored(add_client, pay, db):
    payer, recipient = add_client(), add_client()

    reference = pay(payer, recipient).json()["reference"]

    row = stored(db, reference)
    values = " ".join(str(getattr(row, column)) for column in Transaction.__table__.columns.keys())
    assert "4242424242424242" not in values
    assert row.card_last4 == "4242"


@pytest.mark.parametrize(
    "written", ["06 12 34 56 77", "+33612345677", "0033 6 12 34 56 77", "06.12.34.56.77"]
)
def test_recipient_can_be_designated_by_phone(add_client, pay, written):
    payer = add_client()
    add_client(phone="+33612345677")

    response = pay(payer, to=written)

    assert response.json()["status"] == "authorized"


def test_recipient_email_is_case_insensitive(add_client, pay):
    payer = add_client()
    add_client(email="lea.martin@orbe.test")

    response = pay(payer, to="  Lea.Martin@ORBE.test ")

    assert response.json()["status"] == "authorized"


@pytest.mark.parametrize(
    ("number", "reason"),
    [
        ("4000 0000 0000 0002", "card_declined"),
        ("4000 0000 0000 0069", "card_expired"),
        ("4000 0000 0000 9995", "insufficient_funds"),
    ],
)
def test_declined_test_cards(add_client, pay, db, number, reason):
    payer, recipient = add_client(), add_client()

    response = pay(payer, recipient, card={**OK_CARD, "number": number})

    assert response.status_code == 201
    assert response.json()["status"] == "declined"
    assert response.json()["decline_reason"] == reason
    assert db.balance(recipient) == 0


@pytest.mark.parametrize(
    ("card", "code"),
    [
        ({"number": "4111 1111 1111 1111"}, "card_not_supported"),
        ({"number": "4242 4242 4242 4241"}, "invalid_card"),
        ({"exp_year": 2020}, "invalid_card"),
        ({"cvc": "12a"}, "invalid_card"),
    ],
)
def test_invalid_cards_are_rejected(add_client, pay, card, code):
    payer, recipient = add_client(), add_client()

    response = pay(payer, recipient, card={**OK_CARD, **card})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == code


def test_unknown_recipient_gets_a_neutral_decline(add_client, pay):
    payer = add_client()

    response = pay(payer, to="personne@orbe.test")

    assert response.status_code == 201
    assert response.json()["status"] == "declined"
    assert response.json()["decline_reason"] == "recipient_not_found"


def test_probe_accounts_cannot_be_paid_by_regular_clients(add_client, pay):
    payer = add_client()
    probe = add_client("Sonde", is_probe=True)

    assert pay(payer, probe).json()["decline_reason"] == "recipient_not_found"


def test_self_transfer_is_refused(add_client, pay):
    payer = add_client()

    response = pay(payer, payer)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "self_transfer"


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"amount": 0}, "validation_error"),
        ({"amount": 50_001}, "amount_too_large"),
        ({"currency": "USD"}, "validation_error"),
        ({"to": "pas-un-contact"}, "invalid_recipient"),
    ],
)
def test_invalid_payment_requests(add_client, pay, body, code):
    payer, recipient = add_client(), add_client()

    response = pay(payer, recipient, **body)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == code


def test_validation_errors_never_echo_the_card_number(add_client, client, auth):
    payer = add_client()
    card = {**OK_CARD, "exp_month": 13}

    response = client.post(
        "/pay",
        json={"recipient": "x@orbe.test", "amount_cents": 100, "card": card},
        headers=auth(payer),
    )

    assert response.status_code == 422
    assert "4242" not in response.text


def test_idempotency_key_is_required(add_client, client, auth):
    payer, recipient = add_client(), add_client()
    headers = auth(payer)
    del headers["Idempotency-Key"]

    response = client.post(
        "/pay",
        json={"recipient": recipient.email, "amount_cents": 100, "card": OK_CARD},
        headers=headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "idempotency_key_required"


def test_replaying_the_same_key_does_not_pay_twice(add_client, pay, db):
    payer, recipient = add_client(), add_client()
    key = str(uuid.uuid4())

    first = pay(payer, recipient, key=key)
    second = pay(payer, recipient, key=key)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["reference"] == first.json()["reference"]
    assert db.balance(recipient) == 1250


def test_reusing_a_key_for_another_payment_is_a_conflict(add_client, pay):
    payer, recipient = add_client(), add_client()
    key = str(uuid.uuid4())

    pay(payer, recipient, key=key, amount=1000)
    response = pay(payer, recipient, key=key, amount=2000)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "idempotency_conflict"


def test_payment_requires_a_valid_token(add_client, client, auth):
    payer = add_client()

    no_token = client.post("/pay", json={}, headers={"Idempotency-Key": str(uuid.uuid4())})
    expired = client.post("/pay", json={}, headers=auth(payer, ttl=-10))

    assert no_token.status_code == expired.status_code == 401


def test_payments_are_rate_limited_per_client(app, add_client, pay):
    from app.ratelimit import SlidingWindowLimiter

    app.state.pay_limiter = SlidingWindowLimiter(limit=2)
    payer, recipient = add_client(), add_client()

    assert pay(payer, recipient).status_code == 201
    assert pay(payer, recipient).status_code == 201
    response = pay(payer, recipient)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"


def test_pool_exhaustion_returns_503_and_leaves_a_pending_payment(app, add_client, pay, db):
    class ExhaustedPool:
        async def authorize(self):
            raise sa_exc.TimeoutError("QueuePool limit reached")

    app.state.authorizer = ExhaustedPool()
    payer, recipient = add_client(), add_client()

    response = pay(payer, recipient)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "service_unavailable"
    assert response.headers["Retry-After"] == "2"
    assert db.balance(recipient) == 0
