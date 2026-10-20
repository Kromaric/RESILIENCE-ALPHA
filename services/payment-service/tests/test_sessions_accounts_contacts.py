from conftest import IBAN_A, IBAN_B, OK_CARD, _open_session
from sqlalchemy import update

from app.models import Session
from app.security import SessionGuard

# --- Sessions et second facteur ----------------------------------------------------


def test_moving_money_requires_a_passkey_session(add_client, pay, auth, client):
    camille, lea = add_client(), add_client()
    password_only = auth(camille, factors=("pwd",))

    response = pay(camille, lea, headers=password_only)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "second_factor_required"
    # La consultation reste possible
    assert client.get("/account", headers=password_only).status_code == 200


def test_a_revoked_session_is_refused(add_client, pay, auth, db):
    camille, lea = add_client(), add_client()
    session = _open_session(db, camille)
    headers = auth(camille, session=session)
    assert pay(camille, lea, headers=headers).status_code == 201

    async def revoke(s):
        await s.execute(update(Session).where(Session.id == session.id).values(status="revoked"))

    db.run(revoke)

    assert pay(camille, lea, headers=auth(camille, session=session)).status_code == 401


def test_session_status_is_cached_for_a_few_seconds(app, add_client, auth, client, db):
    app.state.sessions = SessionGuard(app.state.sessionmaker, ttl_seconds=60)
    camille = add_client()
    session = _open_session(db, camille)
    headers = auth(camille, session=session)
    assert client.get("/account", headers=headers).status_code == 200

    async def revoke(s):
        await s.execute(update(Session).where(Session.id == session.id).values(status="revoked"))

    db.run(revoke)

    # Délai maximal de prise en compte d'une révocation = durée du cache (compromis assumé)
    assert client.get("/account", headers=headers).status_code == 200


def test_a_service_token_only_acts_on_probe_accounts(add_client, pay, auth):
    probe_payer = add_client("Sonde", is_probe=True)
    probe_recipient = add_client("Sonde bénéficiaire", is_probe=True)
    regular = add_client()

    def service(c):
        return auth(c, factors=("pwd",), client_api="orbe-probe", client_type="service")

    assert pay(probe_payer, probe_recipient, headers=service(probe_payer)).status_code == 201
    response = pay(regular, probe_recipient, headers=service(regular))
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "client_not_allowed"


def test_operations_record_their_session(add_client, pay, auth, db):
    from sqlalchemy import select

    from app.models import Transaction

    camille, lea = add_client(), add_client()
    session = _open_session(db, camille)
    reference = pay(camille, lea, headers=auth(camille, session=session)).json()["reference"]

    async def session_of(s):
        return await s.scalar(
            select(Transaction.session_id).where(Transaction.reference == reference)
        )

    assert db.run(session_of) == session.id


# --- Comptes liés ------------------------------------------------------------------


def test_add_several_linked_accounts(add_client, auth, client):
    camille = add_client(payout=False)
    headers = auth(camille)

    first = client.post(
        "/payout-accounts", json={"label": "Banque Démo", "iban": IBAN_A}, headers=headers
    )
    second = client.post(
        "/payout-accounts", json={"label": "Néobanque", "iban": IBAN_B}, headers=headers
    )

    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["is_default"] is True
    assert second.json()["is_default"] is False
    assert first.json()["iban_last4"] == "0189"
    assert IBAN_A.replace(" ", "") not in first.text


def test_invalid_iban_is_rejected(add_client, auth, client):
    camille = add_client(payout=False)

    response = client.post(
        "/payout-accounts",
        json={"label": "Faux", "iban": "FR76 3000 6000 0112 3456 7890 188"},
        headers=auth(camille),
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_iban"


def test_switch_default_and_pay_out_to_a_chosen_account(add_client, auth, client, db):
    camille = add_client(payout=False, balance=5000)
    headers = auth(camille)
    a = client.post("/payout-accounts", json={"label": "A", "iban": IBAN_A}, headers=headers).json()
    b = client.post("/payout-accounts", json={"label": "B", "iban": IBAN_B}, headers=headers).json()

    assert client.post(f"/payout-accounts/{b['id']}/default", headers=headers).json()["is_default"]
    default_payout = client.post(
        "/payouts", json={"amount_cents": 100}, headers=auth(camille)
    ).json()
    chosen_payout = client.post(
        "/payouts", json={"amount_cents": 200, "payout_account_id": a["id"]}, headers=auth(camille)
    ).json()

    assert default_payout["payout_account_id"] == b["id"]
    assert chosen_payout["payout_account_id"] == a["id"]
    accounts = client.get("/payout-accounts", headers=headers).json()
    assert [x["is_default"] for x in accounts] == [True, False]
    assert db.balance(camille) == 4700


def test_deleting_the_default_account_promotes_another(add_client, auth, client):
    camille = add_client(payout=False)
    headers = auth(camille)
    a = client.post("/payout-accounts", json={"label": "A", "iban": IBAN_A}, headers=headers).json()
    client.post("/payout-accounts", json={"label": "B", "iban": IBAN_B}, headers=headers)

    assert client.delete(f"/payout-accounts/{a['id']}", headers=headers).status_code == 204
    remaining = client.get("/payout-accounts", headers=headers).json()
    assert [(x["label"], x["is_default"]) for x in remaining] == [("B", True)]


def test_cannot_use_someone_elses_linked_account(add_client, auth, client):
    camille, lea = add_client(balance=1000), add_client()
    lea_account = client.get("/payout-accounts", headers=auth(lea)).json()[0]["id"]

    response = client.post(
        "/payouts",
        json={"amount_cents": 100, "payout_account_id": lea_account},
        headers=auth(camille),
    )

    assert response.status_code == 404


# --- Contacts ----------------------------------------------------------------------


def test_add_list_pay_and_remove_a_contact(add_client, auth, client, pay, db):
    camille = add_client("Camille Test")
    lea = add_client("Léa Martin", email="lea@orbe.test")
    headers = auth(camille)

    added = client.post(
        "/contacts", json={"contact": "LEA@orbe.test", "alias": "Léa"}, headers=headers
    )
    listed = client.get("/contacts", headers=headers).json()
    paid = pay(camille, recipient_contact=lea.id, amount=700)
    removed = client.delete(f"/contacts/{lea.id}", headers=headers)

    assert added.status_code == 201
    assert [(c["contact_id"], c["display_name"], c["alias"]) for c in listed] == [
        (lea.id, "Léa Martin", "Léa")
    ]
    assert paid.json()["status"] == "authorized"
    assert db.balance(lea) == 700
    assert removed.status_code == 204
    assert client.get("/contacts", headers=headers).json() == []


def test_contact_rules(add_client, auth, client):
    camille = add_client(email="camille@orbe.test")
    add_client(email="lea@orbe.test")
    add_client("Sonde", email="probe@orbe.test", is_probe=True)
    headers = auth(camille)

    unknown = client.post("/contacts", json={"contact": "personne@orbe.test"}, headers=headers)
    myself = client.post("/contacts", json={"contact": "camille@orbe.test"}, headers=headers)
    probe = client.post("/contacts", json={"contact": "probe@orbe.test"}, headers=headers)
    client.post("/contacts", json={"contact": "lea@orbe.test"}, headers=headers)
    twice = client.post("/contacts", json={"contact": "lea@orbe.test"}, headers=headers)

    assert unknown.json()["detail"]["code"] == "contact_not_found"
    assert myself.json()["detail"]["code"] == "self_contact"
    assert probe.json()["detail"]["code"] == "contact_not_found"
    assert twice.json()["detail"]["code"] == "contact_exists"


def test_cannot_pay_a_non_contact_by_contact_id(add_client, pay):
    camille, lea = add_client(), add_client()

    response = pay(camille, recipient_contact=lea.id)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "not_a_contact"


def test_pay_needs_exactly_one_recipient(add_client, auth, client):
    camille, lea = add_client(), add_client()

    both = client.post(
        "/pay",
        json={
            "recipient": lea.email,
            "recipient_contact": lea.id,
            "amount_cents": 100,
            "card": OK_CARD,
        },
        headers=auth(camille),
    )

    assert both.status_code == 422
