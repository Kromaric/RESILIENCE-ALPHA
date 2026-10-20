import re
from datetime import timedelta

from conftest import OK_CARD
from sqlalchemy import update

from app.db import utcnow
from app.models import PaymentRequest


def ask(client, auth, requester, payer_contact, amount=800, **body):
    return client.post(
        "/requests",
        json={"payer": payer_contact, "amount_cents": amount, "description": "Covoiturage", **body},
        headers=auth(requester),
    )


# --- Demandes d'argent ----------------------------------------------------------------


def test_create_a_request(add_client, client, auth):
    nathan, camille = add_client("Nathan Moreau"), add_client("Camille Test")

    response = ask(client, auth, nathan, camille.phone)

    assert response.status_code == 201
    body = response.json()
    assert re.fullmatch(r"rq_[0-9a-f]{8}", body["reference"])
    assert (body["role"], body["counterparty"], body["status"]) == (
        "outgoing",
        "Camille Test",
        "pending",
    )


def test_payer_sees_the_request_and_pays_it(add_client, client, auth, db):
    nathan, camille = add_client("Nathan Moreau"), add_client("Camille Test")
    reference = ask(client, auth, nathan, camille.email, amount=800).json()["reference"]

    incoming = client.get("/requests?role=incoming", headers=auth(camille)).json()["items"]
    paid = client.post(f"/requests/{reference}/pay", json={"card": OK_CARD}, headers=auth(camille))

    assert [(r["reference"], r["counterparty"]) for r in incoming] == [(reference, "Nathan Moreau")]
    assert paid.status_code == 201
    assert paid.json()["status"] == "authorized"
    assert paid.json()["amount_cents"] == 800
    assert db.balance(nathan) == 800
    outgoing = client.get("/requests?role=outgoing", headers=auth(nathan)).json()["items"]
    assert outgoing[0]["status"] == "paid"


def test_a_request_cannot_be_paid_twice(add_client, client, auth, db):
    nathan, camille = add_client(), add_client()
    reference = ask(client, auth, nathan, camille.email).json()["reference"]

    client.post(f"/requests/{reference}/pay", json={"card": OK_CARD}, headers=auth(camille))
    again = client.post(f"/requests/{reference}/pay", json={"card": OK_CARD}, headers=auth(camille))

    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "request_not_pending"
    assert db.balance(nathan) == 800


def test_a_declined_card_leaves_the_request_payable(add_client, client, auth):
    nathan, camille = add_client(), add_client()
    reference = ask(client, auth, nathan, camille.email).json()["reference"]
    declined_card = {**OK_CARD, "number": "4000 0000 0000 0002"}

    declined = client.post(
        f"/requests/{reference}/pay", json={"card": declined_card}, headers=auth(camille)
    )
    retried = client.post(
        f"/requests/{reference}/pay", json={"card": OK_CARD}, headers=auth(camille)
    )

    assert declined.json()["status"] == "declined"
    assert retried.json()["status"] == "authorized"


def test_requester_cannot_pay_their_own_request(add_client, client, auth):
    nathan, camille = add_client(), add_client()
    reference = ask(client, auth, nathan, camille.email).json()["reference"]

    response = client.post(
        f"/requests/{reference}/pay", json={"card": OK_CARD}, headers=auth(nathan)
    )

    assert response.status_code == 403


def test_payer_declines_and_requester_cancels(add_client, client, auth):
    nathan, camille = add_client(), add_client()
    first = ask(client, auth, nathan, camille.email).json()["reference"]
    second = ask(client, auth, nathan, camille.email).json()["reference"]

    declined = client.post(f"/requests/{first}/decline", headers=auth(camille))
    cancelled = client.post(f"/requests/{second}/cancel", headers=auth(nathan))
    wrong_side = client.post(f"/requests/{first}/cancel", headers=auth(camille))

    assert declined.json()["status"] == "declined"
    assert cancelled.json()["status"] == "cancelled"
    assert wrong_side.status_code == 403


def test_unknown_payer_gets_a_neutral_failure(add_client, client, auth):
    nathan = add_client()

    response = ask(client, auth, nathan, "personne@orbe.test")

    assert response.status_code == 201
    assert (response.json()["status"], response.json()["failure_reason"]) == (
        "failed",
        "recipient_not_found",
    )


def test_cannot_request_money_from_oneself(add_client, client, auth):
    nathan = add_client()

    assert ask(client, auth, nathan, nathan.email).json()["detail"]["code"] == "self_request"


def test_pending_requests_are_capped(app, add_client, client, auth):
    nathan, camille = add_client(), add_client()
    app.state.settings.max_pending_requests = 2
    try:
        ask(client, auth, nathan, camille.email)
        ask(client, auth, nathan, camille.email)
        response = ask(client, auth, nathan, camille.email)
    finally:
        app.state.settings.max_pending_requests = 20

    assert response.json()["detail"]["code"] == "too_many_pending_requests"


def test_expired_requests_cannot_be_paid(add_client, client, auth, db):
    nathan, camille = add_client(), add_client()
    reference = ask(client, auth, nathan, camille.email).json()["reference"]

    async def age(session):
        await session.execute(
            update(PaymentRequest)
            .where(PaymentRequest.reference == reference)
            .values(expires_at=utcnow() - timedelta(seconds=1))
        )

    db.run(age)
    response = client.post(
        f"/requests/{reference}/pay", json={"card": OK_CARD}, headers=auth(camille)
    )

    assert response.status_code == 409
    listed = client.get("/requests", headers=auth(nathan)).json()["items"]
    assert listed[0]["status"] == "expired"


# --- QR code --------------------------------------------------------------------------


def test_qr_token_identifies_the_recipient(add_client, client, auth, pay, db):
    camille, lea = add_client("Camille Test"), add_client("Léa Martin")

    qr = client.get("/qr", headers=auth(lea)).json()
    paid = pay(camille, recipient_qr=qr["qr_token"], amount=1500)

    assert qr["payload"] == f"orbe://pay?to={qr['qr_token']}"
    assert qr["display_name"] == "Léa Martin"
    assert len(qr["qr_token"]) == 22
    assert paid.json()["status"] == "authorized"
    assert db.balance(lea) == 1500


def test_qr_token_is_stable_until_rotated(add_client, client, auth, pay):
    camille, lea = add_client(), add_client()

    first = client.get("/qr", headers=auth(lea)).json()["qr_token"]
    same = client.get("/qr", headers=auth(lea)).json()["qr_token"]
    rotated = client.post("/qr/rotate", headers=auth(lea)).json()["qr_token"]

    assert first == same != rotated
    assert pay(camille, recipient_qr=first).json()["decline_reason"] == "recipient_not_found"
    assert pay(camille, recipient_qr=rotated).json()["status"] == "authorized"


def test_pay_needs_exactly_one_recipient(add_client, client, auth):
    camille, lea = add_client(), add_client()
    token = client.get("/qr", headers=auth(lea)).json()["qr_token"]

    both = client.post(
        "/pay",
        json={"recipient": lea.email, "recipient_qr": token, "amount_cents": 100, "card": OK_CARD},
        headers=auth(camille),
    )
    none = client.post("/pay", json={"amount_cents": 100, "card": OK_CARD}, headers=auth(camille))

    assert both.status_code == none.status_code == 422
