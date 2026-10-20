import json
import logging
from datetime import timedelta

import jwt

from app.db import utcnow
from app.logging_setup import JsonFormatter
from app.models import Client
from app.ratelimit import SlidingWindowLimiter


def test_login_returns_rs256_jwt(add_client, login, private_key):
    client = add_client()

    response = login()

    assert response.status_code == 200
    body = response.json()
    assert body["mfa_required"] is False
    assert body["passkey_enrollment_required"] is True
    token = body["token"]
    assert token["token_type"] == "bearer"
    assert token["expires_in"] == 900
    assert token["factors"] == ["pwd"]
    claims = jwt.decode(
        token["access_token"],
        private_key.public_key(),
        algorithms=["RS256"],
        audience="orbe",
        issuer="orbe-auth",
    )
    assert claims["sub"] == client.id
    assert claims["email"] == "camille@orbe.test"
    assert claims["exp"] - claims["iat"] == 900
    assert claims["jti"] == body["session_id"]
    assert (claims["amr"], claims["cid"], claims["cty"]) == (["pwd"], "orbe-web", "application")


def test_login_normalizes_email(add_client, login):
    add_client()

    assert login(email="  Camille@ORBE.test ").status_code == 200


def test_wrong_password_and_unknown_email_get_the_same_answer(add_client, login):
    add_client()

    wrong_password = login(password="pas-le-bon")
    unknown_email = login(email="inconnu@orbe.test")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["detail"]["code"] == "invalid_credentials"


def test_account_is_locked_after_five_failures(add_client, login, db):
    client = add_client()

    for _ in range(5):
        assert login(password="pas-le-bon").status_code == 401
    response = login()

    assert response.status_code == 423
    assert response.json()["detail"]["code"] == "account_locked"
    assert 0 < int(response.headers["Retry-After"]) <= 600
    stored = db.get(Client, client.id)
    assert stored.failed_logins == 0
    assert stored.locked_until is not None


def test_success_below_threshold_resets_the_failure_counter(add_client, login, db):
    client = add_client()

    for _ in range(4):
        login(password="pas-le-bon")
    assert db.get(Client, client.id).failed_logins == 4

    assert login().status_code == 200
    assert db.get(Client, client.id).failed_logins == 0


def test_expired_lock_allows_login(add_client, login, db):
    client = add_client(locked_until=utcnow() - timedelta(seconds=1))

    assert login().status_code == 200
    assert db.get(Client, client.id).locked_until is None


def test_login_attempts_are_rate_limited_per_ip(app, add_client, login):
    add_client()
    app.state.login_limiter = SlidingWindowLimiter(limit=3)

    for _ in range(3):
        assert login(password="pas-le-bon").status_code == 401
    response = login()

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "too_many_attempts"
    assert response.headers["Retry-After"] == "60"


def test_password_is_never_logged(add_client, login, caplog):
    add_client()
    secret = "mot-de-passe-tres-secret"

    with caplog.at_level(logging.INFO):
        login(password=secret)

    formatter = JsonFormatter()
    lines = [formatter.format(record) for record in caplog.records]
    assert any(json.loads(line)["msg"] == "login_failed" for line in lines)
    assert all(secret not in line for line in lines)
