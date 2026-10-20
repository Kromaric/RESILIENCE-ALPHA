import json
import logging

import pytest
from conftest import bearer

from app.logging_setup import JsonFormatter
from app.models import Client
from app.ratelimit import SlidingWindowLimiter

STRONG_PASSWORD = "correct-cheval-batterie"


def register(client, **overrides):
    body = {
        "email": "nathan@orbe.test",
        "phone": "06 12 34 56 75",
        "display_name": "Nathan Moreau",
        "password": STRONG_PASSWORD,
        **overrides,
    }
    return client.post("/register", json=body)


def test_register_then_log_in(client, db):
    response = register(client, email="  Nathan@ORBE.test ", display_name="  Nathan   Moreau ")

    assert response.status_code == 201
    body = response.json()
    assert (body["email"], body["display_name"], body["phone_masked"]) == (
        "nathan@orbe.test",
        "Nathan Moreau",
        "+33 6 •• •• •• 75",
    )
    stored = db.get(Client, body["client_id"])
    assert stored.phone == "+33612345675"
    assert stored.is_probe is False
    assert stored.password_hash.startswith("$argon2id$")

    login = client.post(
        "/login", json={"email": "nathan@orbe.test", "password": STRONG_PASSWORD}
    ).json()
    assert login["passkey_enrollment_required"] is True
    me = client.get("/me", headers=bearer(login["token"]["access_token"])).json()
    assert me["client_id"] == body["client_id"]


def test_cannot_register_a_probe_account(client, db):
    response = client.post(
        "/register",
        json={
            "email": "sonde@orbe.test",
            "phone": "+33600000099",
            "display_name": "Fausse sonde",
            "password": STRONG_PASSWORD,
            "is_probe": True,
        },
    )

    assert response.status_code == 201
    assert db.get(Client, response.json()["client_id"]).is_probe is False


def test_email_and_phone_are_unique(client, add_client):
    add_client(email="camille@orbe.test", phone="+33612345678")

    same_email = register(client, email="Camille@orbe.test")
    same_phone = register(client, phone="0033 6 12 34 56 78")

    assert (same_email.status_code, same_email.json()["detail"]["code"]) == (409, "email_taken")
    assert (same_phone.status_code, same_phone.json()["detail"]["code"]) == (409, "phone_taken")


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"email": "pas-un-email"}, "invalid_email"),
        ({"phone": "123456789"}, "invalid_phone"),
        ({"phone": "1"}, "validation_error"),
        ({"password": "court"}, "weak_password"),
        ({"password": "azerty123456"}, "weak_password"),
        ({"password": "aaaaaaaaaaaaaaaa"}, "weak_password"),
        ({"password": "nathan-2026-orbe"}, "weak_password"),  # contient l'email
    ],
)
def test_invalid_registrations(client, overrides, code):
    response = register(client, **overrides)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == code


def test_registrations_are_rate_limited_per_ip(client, app):
    app.state.register_limiter = SlidingWindowLimiter(limit=2)

    register(client, email="a@orbe.test", phone="0612345601")
    register(client, email="b@orbe.test", phone="0612345602")
    response = register(client, email="c@orbe.test", phone="0612345603")

    assert response.status_code == 429


def test_password_is_never_logged(client, caplog):
    with caplog.at_level(logging.INFO):
        register(client)

    lines = [JsonFormatter().format(record) for record in caplog.records]
    assert any(json.loads(line)["msg"] == "account_registered" for line in lines)
    assert all(STRONG_PASSWORD not in line and "nathan@orbe.test" not in line for line in lines)
