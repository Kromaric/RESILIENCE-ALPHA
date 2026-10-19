from pathlib import Path

from conftest import OK_CARD

from app.models import Client, Transaction

DECLINED_CARD = {**OK_CARD, "number": "4000 0000 0000 0002"}


# --- Historique -----------------------------------------------------------------------


def test_history_shows_sent_and_received_with_counterparty(add_client, pay, client, auth):
    camille, lea, hugo = add_client("Camille Test"), add_client("Léa Martin"), add_client("Hugo")
    pay(camille, lea, amount=1250, description="Ciné")
    pay(hugo, camille, amount=2500, description="Pizza vendredi")

    items = client.get("/transactions", headers=auth(camille)).json()["items"]

    assert [
        (i["direction"], i["counterparty"], i["amount_cents"], i["description"]) for i in items
    ] == [
        ("received", "Hugo", 2500, "Pizza vendredi"),
        ("sent", "Léa Martin", 1250, "Ciné"),
    ]


def test_recipient_does_not_see_declined_attempts(add_client, pay, client, auth):
    camille, lea = add_client(), add_client()
    pay(camille, lea, card=DECLINED_CARD)

    payer_view = client.get("/transactions", headers=auth(camille)).json()["items"]
    recipient_view = client.get("/transactions", headers=auth(lea)).json()["items"]

    assert [i["status"] for i in payer_view] == ["declined"]
    assert recipient_view == []


def test_history_filters_and_paginates(add_client, pay, client, auth):
    camille, lea = add_client(), add_client()
    for amount in (100, 200, 300):
        pay(camille, lea, amount=amount)
    pay(camille, lea, card=DECLINED_CARD)

    declined = client.get("/transactions?status=declined", headers=auth(camille)).json()
    received = client.get("/transactions?direction=received", headers=auth(camille)).json()
    page1 = client.get("/transactions?limit=2", headers=auth(camille)).json()
    page2 = client.get(
        f"/transactions?limit=2&cursor={page1['next_cursor']}", headers=auth(camille)
    ).json()

    assert len(declined["items"]) == 1
    assert received["items"] == []
    assert len(page1["items"]) == 2 and page1["next_cursor"]
    assert len(page2["items"]) == 2 and page2["next_cursor"] is None
    seen = {i["reference"] for i in page1["items"] + page2["items"]}
    assert len(seen) == 4


def test_a_transaction_is_visible_only_to_its_parties(add_client, pay, client, auth):
    camille, lea, stranger = add_client(), add_client(), add_client()
    reference = pay(camille, lea).json()["reference"]

    assert client.get(f"/transactions/{reference}", headers=auth(lea)).status_code == 200
    assert client.get(f"/transactions/{reference}", headers=auth(stranger)).status_code == 404


# --- Remboursement --------------------------------------------------------------------


def test_recipient_refunds_a_payment(add_client, pay, client, auth, db):
    camille, lea = add_client("Camille Test"), add_client("Léa Martin")
    original = pay(camille, lea, amount=1250, description="Ciné").json()["reference"]

    response = client.post(f"/transactions/{original}/refund", headers=auth(lea))

    assert response.status_code == 201
    assert response.json()["refunded"] == original
    assert response.json()["status"] == "completed"
    assert db.get(Client, lea.id).balance_cents == 0
    statuses = {
        i["reference"]: i
        for i in client.get("/transactions", headers=auth(camille)).json()["items"]
    }
    assert statuses[original]["status"] == "refunded"
    refund_item = statuses[response.json()["reference"]]
    assert (refund_item["direction"], refund_item["counterparty"]) == ("received", "Léa Martin")
    assert refund_item["description"] == "Remboursement · Ciné"


def test_only_the_recipient_can_refund(add_client, pay, client, auth):
    camille, lea, stranger = add_client(), add_client(), add_client()
    reference = pay(camille, lea).json()["reference"]

    by_payer = client.post(f"/transactions/{reference}/refund", headers=auth(camille))
    by_stranger = client.post(f"/transactions/{reference}/refund", headers=auth(stranger))

    assert by_payer.status_code == 403
    assert by_stranger.status_code == 404


def test_a_payment_is_refunded_only_once(add_client, pay, client, auth, db):
    camille, lea = add_client(), add_client(balance=5000)
    reference = pay(camille, lea).json()["reference"]

    assert client.post(f"/transactions/{reference}/refund", headers=auth(lea)).status_code == 201
    again = client.post(f"/transactions/{reference}/refund", headers=auth(lea))

    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "already_refunded"
    assert db.get(Client, lea.id).balance_cents == 5000


def test_refund_replay_returns_the_same_refund(add_client, pay, client, auth, db):
    camille, lea = add_client(), add_client()
    reference = pay(camille, lea).json()["reference"]
    headers = auth(lea)

    first = client.post(f"/transactions/{reference}/refund", headers=headers)
    second = client.post(f"/transactions/{reference}/refund", headers=headers)

    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json() == second.json()


def test_refund_needs_enough_balance(add_client, pay, client, auth):
    camille, lea = add_client(), add_client()
    reference = pay(camille, lea, amount=1250).json()["reference"]
    client.post("/payouts", json={"amount_cents": 1000}, headers=auth(lea))

    response = client.post(f"/transactions/{reference}/refund", headers=auth(lea))

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "insufficient_balance"


def test_declined_payments_are_unknown_to_the_recipient(add_client, pay, client, auth):
    camille, lea = add_client(), add_client()
    reference = pay(camille, lea, card=DECLINED_CARD).json()["reference"]

    response = client.post(f"/transactions/{reference}/refund", headers=auth(lea))

    assert response.status_code == 404


# --- Compte et retraits ---------------------------------------------------------------


def test_account_shows_balance_and_linked_account(add_client, client, auth):
    camille = add_client(balance=4200)

    assert client.get("/account", headers=auth(camille)).json() == {
        "balance_cents": 4200,
        "currency": "EUR",
        "payout_account": {"label": "Banque Démo", "iban_last4": "0142"},
    }


def test_payout_debits_the_balance(add_client, client, auth, db):
    camille = add_client(balance=4200)

    response = client.post("/payouts", json={"amount_cents": 1200}, headers=auth(camille))

    assert response.status_code == 201
    assert response.json()["status"] == "completed"
    assert db.get(Client, camille.id).balance_cents == 3000
    item = client.get("/transactions", headers=auth(camille)).json()["items"][0]
    assert (item["type"], item["counterparty"]) == ("payout", "Compte lié")
    assert item["description"] == "Retrait vers Banque Démo •••• 0142"


def test_payout_cannot_exceed_the_balance(add_client, client, auth, db):
    camille = add_client(balance=500)

    response = client.post("/payouts", json={"amount_cents": 501}, headers=auth(camille))

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "insufficient_balance"
    assert db.get(Client, camille.id).balance_cents == 500


def test_payout_needs_a_linked_account(add_client, client, auth):
    camille = add_client(balance=500, payout=False)

    response = client.post("/payouts", json={"amount_cents": 100}, headers=auth(camille))

    assert response.json()["detail"]["code"] == "no_payout_account"


def test_payout_replay_does_not_debit_twice(add_client, client, auth, db):
    camille = add_client(balance=1000)
    headers = auth(camille)

    client.post("/payouts", json={"amount_cents": 400}, headers=headers)
    replay = client.post("/payouts", json={"amount_cents": 400}, headers=headers)

    assert replay.status_code == 200
    assert db.get(Client, camille.id).balance_cents == 600


def test_orm_model_matches_the_reference_schema():
    schema = (Path(__file__).parents[3] / "infra/mariadb/init/01-schema.sql").read_text("utf-8")
    table = schema.split("CREATE TABLE transactions", 1)[1].split(") ENGINE", 1)[0]

    for column in Transaction.__table__.columns:
        assert f"    {column.name} " in table, f"colonne {column.name} absente du schéma SQL"
