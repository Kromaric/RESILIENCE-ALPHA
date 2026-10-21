from datetime import timedelta

import jwt
from conftest import PASSWORD, bearer
from sqlalchemy import update

from app.db import utcnow
from app.models import Operator, OperatorSession


def operator_login(client, email="ops@orbe.test", password=PASSWORD):
    return client.post("/operators/login", json={"email": email, "password": password})


def test_operator_login_returns_a_back_office_token(add_operator, client, private_key, db):
    created = add_operator()

    response = operator_login(client)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "operator"
    claims = jwt.decode(
        body["access_token"], private_key.public_key(), algorithms=["RS256"], audience="orbe-bo"
    )
    assert (claims["sub"], claims["typ"], claims["role"], claims["amr"]) == (
        created.id,
        "operator",
        "operator",
        ["pwd"],
    )
    assert db.get(OperatorSession, claims["jti"]).status == "active"
    assert db.get(Operator, created.id).last_login_at is not None


def test_me_reflects_the_current_role(add_operator, client, db):
    created = add_operator(role="viewer")
    token = operator_login(client).json()["access_token"]

    async def promote(session):
        await session.execute(
            update(Operator).where(Operator.id == created.id).values(role="operator")
        )

    db.run(promote)
    me = client.get("/operators/me", headers=bearer(token)).json()

    assert (me["operator_id"], me["role"], me["email"]) == (created.id, "operator", "ops@orbe.test")


def test_wrong_password_and_unknown_email_look_the_same(add_operator, client):
    add_operator()

    wrong = operator_login(client, password="mauvais-mot-de-passe")
    unknown = operator_login(client, email="personne@orbe.test")

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_five_failures_lock_the_operator(add_operator, client):
    add_operator()

    for _ in range(5):
        assert operator_login(client, password="mauvais-mot-de-passe").status_code == 401

    locked = operator_login(client)
    assert locked.status_code == 423
    assert "Retry-After" in locked.headers


def test_disabled_operator_cannot_log_in_or_use_its_token(add_operator, client, db):
    created = add_operator()
    token = operator_login(client).json()["access_token"]

    async def disable(session):
        await session.execute(
            update(Operator).where(Operator.id == created.id).values(active=False)
        )

    db.run(disable)

    assert operator_login(client).status_code == 401
    assert client.get("/operators/me", headers=bearer(token)).status_code == 401


def test_logout_revokes_the_session(add_operator, client):
    add_operator()
    headers = bearer(operator_login(client).json()["access_token"])

    assert client.post("/operators/logout", headers=headers).status_code == 204
    assert client.get("/operators/me", headers=headers).status_code == 401


def test_expired_session_is_refused(add_operator, client, db, private_key):
    add_operator()
    token = operator_login(client).json()["access_token"]
    session_id = jwt.decode(token, options={"verify_signature": False})["jti"]

    async def expire(session):
        await session.execute(
            update(OperatorSession)
            .where(OperatorSession.id == session_id)
            .values(expires_at=utcnow() - timedelta(seconds=1))
        )

    db.run(expire)

    assert client.get("/operators/me", headers=bearer(token)).status_code == 401
    assert db.get(OperatorSession, session_id).status == "expired"


def test_client_and_operator_tokens_are_not_interchangeable(
    add_operator, add_client, token, client
):
    add_operator()
    add_client()
    operator_token = operator_login(client).json()["access_token"]
    client_token = token()

    assert client.get("/operators/me", headers=bearer(client_token)).status_code == 401
    assert client.get("/me", headers=bearer(operator_token)).status_code == 401


def test_a_client_account_cannot_log_in_to_the_back_office(add_client, client):
    add_client()

    assert operator_login(client, email="camille@orbe.test").status_code == 401
