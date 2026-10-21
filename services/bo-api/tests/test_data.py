import logging
from datetime import timedelta

import pytest
from conftest import bearer
from sqlalchemy import insert, update
from sqlalchemy.exc import OperationalError

from app.db import (
    bo_clients,
    ledger_accounts,
    ledger_entries,
    payment_requests,
    payout_accounts,
    sessions,
    transactions,
    utcnow,
)

CAMILLE, LEA, HUGO, PROBE = "c-camille", "c-lea", "c-hugo", "c-probe"
CARD, PAYOUTS = "acct-card", "acct-payouts"


def client_row(id_, name, minutes_ago, **fields):
    return {
        "id": id_,
        "display_name": name,
        "email_masked": f"{name[0].lower()}•••@orbe.test",
        "phone_masked": "+33 6 •• •• •• 78",
        "is_probe": False,
        "failed_logins": 0,
        "locked_until": None,
        "face_enrolled": False,
        "created_at": utcnow() - timedelta(minutes=minutes_ago),
        **fields,
    }


def tx(id_, ref, type_, payer, recipient, amount, status, minutes_ago, **fields):
    now = utcnow()
    return {
        "id": id_,
        "reference": ref,
        "type": type_,
        "payer_id": payer,
        "recipient_id": recipient,
        "parent_id": None,
        "payout_account_id": None,
        "amount_cents": amount,
        "currency": "EUR",
        "description": None,
        "card_brand": "visa" if type_ == "payment" else None,
        "card_last4": "4242" if type_ == "payment" else None,
        "status": status,
        "decline_reason": None,
        "created_at": now - timedelta(minutes=minutes_ago),
        "updated_at": now - timedelta(minutes=minutes_ago),
        **fields,
    }


def entries(tx_id, debit_account, credit_account, amount):
    return [
        {"transaction_id": tx_id, "account_id": debit_account, "direction": "debit",
         "amount_cents": amount, "created_at": utcnow()},
        {"transaction_id": tx_id, "account_id": credit_account, "direction": "credit",
         "amount_cents": amount, "created_at": utcnow()},
    ]  # fmt: skip


@pytest.fixture
def seeded(db):
    """Jeu cohérent : A paiement autorisé, B paiement remboursé par R, W retrait, D refus ;
    P opération de la sonde (exclue partout sauf du contrôle comptable)."""
    db(
        insert(bo_clients).values(
            [
                client_row(CAMILLE, "Camille Test", 60 * 24 * 20, face_enrolled=True),
                client_row(LEA, "Léa Martin", 60),
                client_row(
                    HUGO,
                    "Hugo 100%_Bernard",
                    30,
                    failed_logins=0,
                    locked_until=utcnow() + timedelta(minutes=5),
                ),
                client_row(PROBE, "Sonde payeur", 10, is_probe=True),
            ]
        ),
        insert(ledger_accounts).values(
            [
                {
                    "id": CARD,
                    "type": "counterpart",
                    "code": "card_settlement",
                    "label": "Encaissements carte",
                    "balance_cents": -2100,
                    "client_id": None,
                },
                {
                    "id": PAYOUTS,
                    "type": "counterpart",
                    "code": "payouts",
                    "label": "Retraits",
                    "balance_cents": 500,
                    "client_id": None,
                },
                {
                    "id": "acct-camille",
                    "type": "client",
                    "code": None,
                    "label": "Camille",
                    "balance_cents": 0,
                    "client_id": CAMILLE,
                },
                {
                    "id": "acct-lea",
                    "type": "client",
                    "code": None,
                    "label": "Léa",
                    "balance_cents": 1500,
                    "client_id": LEA,
                },
                {
                    "id": "acct-hugo",
                    "type": "client",
                    "code": None,
                    "label": "Hugo",
                    "balance_cents": 0,
                    "client_id": HUGO,
                },
                {
                    "id": "acct-probe",
                    "type": "client",
                    "code": None,
                    "label": "Sonde",
                    "balance_cents": 100,
                    "client_id": PROBE,
                },
            ]
        ),  # fmt: skip
        insert(payout_accounts).values(
            id="pa-lea",
            client_id=LEA,
            label="Compte courant",
            iban_last4="0189",
            is_default=True,
            created_at=utcnow(),
        ),  # fmt: skip
        insert(transactions).values(
            [
                tx(
                    "t-a",
                    "tx_aaaaaaaa",
                    "payment",
                    CAMILLE,
                    LEA,
                    2000,
                    "authorized",
                    50,
                    description="Ciné",
                ),
                tx("t-b", "tx_bbbbbbbb", "payment", HUGO, LEA, 1250, "refunded", 40),
                tx(
                    "t-r",
                    "tx_rrrrrrrr",
                    "refund",
                    LEA,
                    HUGO,
                    1250,
                    "authorized",
                    35,
                    parent_id="t-b",
                ),
                tx(
                    "t-w",
                    "tx_wwwwwwww",
                    "payout",
                    LEA,
                    None,
                    500,
                    "completed",
                    20,
                    payout_account_id="pa-lea",
                ),
                tx(
                    "t-d",
                    "tx_dddddddd",
                    "payment",
                    CAMILLE,
                    HUGO,
                    999,
                    "declined",
                    10,
                    decline_reason="card_declined",
                ),
                tx("t-p", "tx_pppppppp", "payment", PROBE, PROBE, 100, "authorized", 5),
            ]
        ),  # fmt: skip
        insert(ledger_entries).values(
            entries("t-a", CARD, "acct-lea", 2000)
            + entries("t-b", CARD, "acct-lea", 1250)
            + entries("t-r", "acct-lea", CARD, 1250)
            + entries("t-w", "acct-lea", PAYOUTS, 500)
            + entries("t-p", CARD, "acct-probe", 100)
        ),
        insert(payment_requests).values(
            [
                {
                    "id": "r-1",
                    "reference": "rq_11111111",
                    "requester_id": LEA,
                    "payer_id": HUGO,
                    "transaction_id": "t-b",
                    "amount_cents": 1250,
                    "currency": "EUR",
                    "description": None,
                    "status": "paid",
                    "failure_reason": None,
                    "created_at": utcnow() - timedelta(minutes=45),
                    "expires_at": utcnow() + timedelta(days=7),
                    "updated_at": utcnow(),
                },
                {
                    "id": "r-2",
                    "reference": "rq_22222222",
                    "requester_id": LEA,
                    "payer_id": CAMILLE,
                    "transaction_id": None,
                    "amount_cents": 800,
                    "currency": "EUR",
                    "description": "Resto",
                    "status": "pending",
                    "failure_reason": None,
                    "created_at": utcnow() - timedelta(minutes=5),
                    "expires_at": utcnow() + timedelta(days=7),
                    "updated_at": utcnow(),
                },
            ]
        ),  # fmt: skip
        insert(sessions).values(
            [
                {
                    "id": "s-1",
                    "client_id": CAMILLE,
                    "status": "active",
                    "opened_at": utcnow(),
                    "expires_at": utcnow() + timedelta(minutes=10),
                },
                {
                    "id": "s-2",
                    "client_id": CAMILLE,
                    "status": "revoked",
                    "opened_at": utcnow(),
                    "expires_at": utcnow() + timedelta(minutes=10),
                },
            ]
        ),  # fmt: skip
    )


@pytest.fixture
def ops(auth):
    return bearer(auth.token("ops@orbe.test"))


@pytest.fixture
def viewer(auth):
    return bearer(auth.token("viewer@orbe.test"))


# --- Indicateurs (viewer) ---------------------------------------------------------------------


def test_summary_excludes_the_probe(client, seeded, viewer):
    response = client.get("/bo/data/summary", headers=viewer)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["clients"] == {"total": 3, "new_7d": 2, "face_enrolled": 1, "locked": 1}
    ops_24h = body["operations_24h"]
    assert ops_24h["count"] == 5
    assert ops_24h["by_type"] == {"payment": 3, "refund": 1, "payout": 1}
    assert (ops_24h["payments_authorized_cents"], ops_24h["refunds_cents"]) == (3250, 1250)
    assert ops_24h["payouts_cents"] == 500
    assert ops_24h["decline_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert ops_24h["decline_reasons"] == [{"key": "card_declined", "count": 1}]
    assert body["requests"] == {"pending": 1, "paid_7d": 1}
    assert body["balances"] == {
        "clients_total_cents": 1500,
        "counterparts_cents": {"card_settlement": -2100, "payouts": 500},
    }


@pytest.mark.parametrize(
    ("metric", "total"),
    [("transactions", 5), ("amount", 3250), ("declines", 1), ("registrations", 2)],
)
def test_series_by_hour(client, seeded, viewer, metric, total):
    response = client.get(
        "/bo/data/series", params={"metric": metric, "interval": "hour"}, headers=viewer
    )

    assert response.status_code == 200, response.text
    points = response.json()["points"]
    assert len(points) == 24
    assert sum(p["value"] for p in points) == total
    assert points[-1]["time"].endswith(":00:00Z")


def test_series_by_day_has_30_points(client, seeded, viewer):
    points = client.get(
        "/bo/data/series", params={"metric": "registrations", "interval": "day"}, headers=viewer
    ).json()["points"]

    assert len(points) == 30
    assert sum(p["value"] for p in points) == 3  # Camille, inscrite il y a 20 jours, comprise


def test_ledger_check_passes_on_consistent_data(client, seeded, viewer):
    body = client.get("/bo/data/ledger/check", headers=viewer).json()

    assert body["ok"] is True, body
    assert (body["transactions_checked"], body["accounts_checked"]) == (6, 6)


def test_ledger_check_reports_anomalies(client, seeded, viewer, db):
    db(
        update(ledger_accounts).where(ledger_accounts.c.id == "acct-lea").values(balance_cents=9),
        insert(ledger_entries).values(
            transaction_id="t-d",
            account_id="acct-hugo",
            direction="credit",
            amount_cents=999,
            created_at=utcnow(),
        ),  # fmt: skip
    )

    body = client.get("/bo/data/ledger/check", headers=viewer).json()

    assert body["ok"] is False
    assert body["unbalanced_transactions"] == ["tx_dddddddd"]
    assert {m["account_id"] for m in body["account_mismatches"]} == {"acct-lea", "acct-hugo"}
    assert body["entries_anomalies"] == [
        {"reference": "tx_dddddddd", "status": "declined", "entries": 1}
    ]


# --- Listes et fiches (operator) ---------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/bo/data/transactions",
        "/bo/data/transactions/tx_aaaaaaaa",
        "/bo/data/clients",
        f"/bo/data/clients/{CAMILLE}",
        "/bo/data/requests",
    ],
)
def test_personal_data_is_reserved_to_operators(client, seeded, viewer, path):
    response = client.get(path, headers=viewer)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "forbidden"


def test_data_requires_a_session(client, seeded):
    assert client.get("/bo/data/summary").status_code == 401


def test_transactions_are_paginated_and_exclude_the_probe(client, seeded, ops):
    first = client.get("/bo/data/transactions", params={"size": 50}, headers=ops).json()
    second = client.get("/bo/data/transactions", params={"page": 2}, headers=ops).json()

    assert (first["total"], first["size"], len(first["items"])) == (5, 3, 3)  # taille plafonnée
    assert [t["reference"] for t in first["items"]] == ["tx_dddddddd", "tx_wwwwwwww", "tx_rrrrrrrr"]
    assert [t["reference"] for t in second["items"]] == ["tx_bbbbbbbb", "tx_aaaaaaaa"]
    payment = second["items"][1]
    assert payment["payer"] == {"client_id": CAMILLE, "display_name": "Camille Test"}
    assert payment["card"] == {"brand": "visa", "last4": "4242"}
    assert first["items"][1]["recipient"] is None  # retrait


@pytest.mark.parametrize(
    ("params", "references"),
    [
        ({"type": "refund"}, ["tx_rrrrrrrr"]),
        ({"status": "declined"}, ["tx_dddddddd"]),
        ({"client_id": HUGO}, ["tx_dddddddd", "tx_rrrrrrrr", "tx_bbbbbbbb"]),
        ({"reference": "tx_aaaaaaaa"}, ["tx_aaaaaaaa"]),
        ({"reference": "tx_pppppppp"}, []),  # sonde
    ],
)
def test_transaction_filters(client, seeded, ops, params, references):
    body = client.get("/bo/data/transactions", params=params, headers=ops).json()

    assert [t["reference"] for t in body["items"]] == references


def test_transaction_detail_links_refund_request_and_entries(client, seeded, ops):
    payment = client.get("/bo/data/transactions/tx_bbbbbbbb", headers=ops).json()
    refund = client.get("/bo/data/transactions/tx_rrrrrrrr", headers=ops).json()
    payout = client.get("/bo/data/transactions/tx_wwwwwwww", headers=ops).json()

    assert (payment["refund_reference"], payment["request_reference"]) == (
        "tx_rrrrrrrr",
        "rq_11111111",
    )
    assert [(e["direction"], e["account_label"]) for e in payment["entries"]] == [
        ("debit", "Encaissements carte"),
        ("credit", "Léa"),
    ]
    assert refund["parent_reference"] == "tx_bbbbbbbb"
    assert payout["payout_account"] == {
        "label": "Compte courant",
        "iban_last4": "0189",
        "is_default": True,
    }


def test_probe_and_unknown_transactions_are_not_found(client, seeded, ops):
    assert client.get("/bo/data/transactions/tx_pppppppp", headers=ops).status_code == 404
    assert client.get("/bo/data/transactions/tx_inconnue", headers=ops).status_code == 404


def test_clients_are_masked_and_exclude_the_probe(client, seeded, ops):
    body = client.get("/bo/data/clients", headers=ops).json()

    assert body["total"] == 3
    hugo, lea, camille = body["items"]
    assert lea["email_masked"] == "l•••@orbe.test"
    assert lea["phone_masked"] == "+33 6 •• •• •• 78"
    assert (lea["balance_cents"], lea["operations_count"]) == (1500, 4)
    assert (hugo["locked"], camille["face_enrolled"]) == (True, True)
    assert all("email" not in key or key == "email_masked" for key in lea)


@pytest.mark.parametrize(
    ("params", "names"),
    [
        ({"q": "léa"}, ["Léa Martin"]),
        ({"q": "100%_"}, ["Hugo 100%_Bernard"]),  # caractères spéciaux du LIKE échappés
        ({"q": "%"}, ["Hugo 100%_Bernard"]),
        ({"locked": "true"}, ["Hugo 100%_Bernard"]),
        ({"locked": "false", "face_enrolled": "true"}, ["Camille Test"]),
    ],
)
def test_client_filters(client, seeded, ops, params, names):
    body = client.get("/bo/data/clients", params=params, headers=ops).json()

    assert [c["display_name"] for c in body["items"]] == names


def test_client_detail(client, seeded, ops):
    body = client.get(f"/bo/data/clients/{LEA}", headers=ops).json()

    assert body["payout_accounts"] == [
        {"label": "Compte courant", "iban_last4": "0189", "is_default": True}
    ]
    assert body["pending_requests"] == 1
    assert [t["reference"] for t in body["recent_transactions"]] == [
        "tx_wwwwwwww",
        "tx_rrrrrrrr",
        "tx_bbbbbbbb",
        "tx_aaaaaaaa",
    ]
    camille = client.get(f"/bo/data/clients/{CAMILLE}", headers=ops).json()
    assert camille["active_sessions"] == 1


def test_probe_client_is_not_found(client, seeded, ops):
    assert client.get(f"/bo/data/clients/{PROBE}", headers=ops).status_code == 404


def test_requests(client, seeded, ops):
    body = client.get("/bo/data/requests", headers=ops).json()
    pending = client.get("/bo/data/requests", params={"status": "pending"}, headers=ops).json()

    assert [r["reference"] for r in body["items"]] == ["rq_22222222", "rq_11111111"]
    assert body["items"][1]["transaction_reference"] == "tx_bbbbbbbb"
    assert [r["reference"] for r in pending["items"]] == ["rq_22222222"]
    assert pending["items"][0]["payer"] == {"client_id": CAMILLE, "display_name": "Camille Test"}


def test_each_consultation_of_personal_data_is_audited(client, seeded, ops, caplog):
    with caplog.at_level(logging.INFO, logger="data"):
        client.get(f"/bo/data/clients/{LEA}", headers=ops)
        client.get("/bo/data/summary", headers=ops)

    audits = [r for r in caplog.records if r.getMessage() == "personal_data_viewed"]
    assert len(audits) == 1  # pas pour les indicateurs agrégés
    assert audits[0].fields["resource"] == "client"
    assert audits[0].fields["client_id"] == LEA
    assert audits[0].fields["operator_email"] == "ops@orbe.test"


def test_database_down_gives_503(app, client, seeded, ops, monkeypatch):
    class Broken:
        async def __aenter__(self):
            raise OperationalError("SELECT 1", {}, Exception("connexion refusée"))

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(app.state, "sessionmaker", lambda: Broken())

    response = client.get("/bo/data/summary", headers=ops)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "database_unavailable"
