from datetime import timedelta

import jwt
import pytest
from conftest import bearer
from soft_authenticator import SoftAuthenticator
from sqlalchemy import update

from app.db import utcnow
from app.models import ClientApi, Passkey, Session
from app.security import hash_api_key


def start_login(login):
    response = login()
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mfa_required"] is True
    return body


def finish_login(client, body, credential):
    return client.post(
        "/login/passkey", json={"session_id": body["session_id"], "credential": credential}
    )


# --- Enregistrement ---------------------------------------------------------------


def test_first_passkey_can_be_registered_from_a_password_session(add_client, enroll, db):
    created = add_client()

    enroll()

    assert db.count(Passkey, Passkey.client_id == created.id) == 1


def test_registration_requires_user_verification_and_the_right_origin(add_client, client, token):
    add_client()
    headers = bearer(token())
    options = client.post("/passkeys/register/options", headers=headers).json()

    response = client.post(
        "/passkeys/register",
        json={"credential": SoftAuthenticator().register(options, origin="https://evil.test")},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_passkey"


def password_only_session(client, db, client_row):
    """Session « mot de passe seul » : ce qu'obtiendrait quelqu'un qui ne connaît que le mot
    de passe d'un compte qui a déjà une passkey (simulé directement en base)."""
    session = db.add(
        Session(
            id="00000000-0000-0000-0000-0000000000aa",
            client_id=client_row.id,
            client_api_id="orbe-web",
            status="active",
            factors="pwd",
            expires_at=utcnow() + timedelta(minutes=5),
        )
    )
    return bearer(
        client.app.state.tokens.issue(client_row.id, client_row.email, session_id=session.id)
    )


def test_a_password_alone_cannot_add_or_remove_devices(add_client, enroll, client, db):
    created = add_client()
    enroll()
    headers = password_only_session(client, db, created)

    assert client.post("/passkeys/register/options", headers=headers).status_code == 403
    passkey_id = client.get("/passkeys", headers=headers).json()[0]["id"]
    assert client.delete(f"/passkeys/{passkey_id}", headers=headers).status_code == 403


# --- Connexion en deux étapes -----------------------------------------------------


def test_login_with_a_passkey(add_client, enroll, login, client, private_key, db):
    created = add_client()
    authenticator = enroll()

    body = start_login(login)
    assert body["token"] is None
    assert body["webauthn_options"]["userVerification"] == "required"
    assert body["webauthn_options"]["allowCredentials"][0]["id"] == authenticator.id

    response = finish_login(client, body, authenticator.login(body["webauthn_options"]))

    assert response.status_code == 200, response.text
    token = response.json()
    assert token["factors"] == ["pwd", "passkey"]
    claims = jwt.decode(
        token["access_token"], private_key.public_key(), algorithms=["RS256"], audience="orbe"
    )
    assert claims["amr"] == ["pwd", "passkey"]
    assert claims["jti"] == body["session_id"]
    session = db.get(Session, body["session_id"])
    assert (session.status, session.webauthn_challenge) == ("active", None)
    assert db.get(Passkey, session.passkey_id).sign_count == 1
    me = client.get("/me", headers=bearer(token["access_token"])).json()
    assert (me["client_id"], me["factors"], me["passkey_count"]) == (
        created.id,
        ["pwd", "passkey"],
        1,
    )


def test_pending_session_cannot_be_used_as_a_token(add_client, enroll, login, client, private_key):
    add_client()
    enroll()
    body = start_login(login)

    # Un jeton forgé sur une session « en attente de 2FA » est refusé
    pending = client.app.state.tokens.issue("x", "x", session_id=body["session_id"])

    assert client.get("/me", headers=bearer(pending)).status_code == 401


@pytest.mark.parametrize(
    "tamper",
    [
        {"user_verified": False},  # Face ID refusé ou contourné
        {"origin": "https://evil.test"},  # page d'hameçonnage
    ],
)
def test_second_factor_is_refused_when_the_device_response_is_wrong(
    add_client, enroll, login, client, tamper
):
    add_client()
    authenticator = enroll()
    body = start_login(login)

    response = finish_login(client, body, authenticator.login(body["webauthn_options"], **tamper))

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "second_factor_failed"


def test_another_device_cannot_answer(add_client, enroll, login, client):
    add_client()
    enroll()
    body = start_login(login)

    response = finish_login(client, body, SoftAuthenticator().login(body["webauthn_options"]))

    assert response.status_code == 401


def test_a_challenge_cannot_be_replayed(add_client, enroll, login, client):
    add_client()
    authenticator = enroll()
    body = start_login(login)
    credential = authenticator.login(body["webauthn_options"])

    assert finish_login(client, body, credential).status_code == 200
    assert finish_login(client, body, credential).status_code == 401


def test_a_cloned_passkey_is_detected_by_its_counter(add_client, enroll, login, client):
    add_client()
    authenticator = enroll()
    first = start_login(login)
    assert (
        finish_login(client, first, authenticator.login(first["webauthn_options"])).status_code
        == 200
    )

    # Le clone repart avec le même compteur : il ne progresse pas
    second = start_login(login)
    clone = authenticator.login(second["webauthn_options"], bump_counter=False)

    assert finish_login(client, second, clone).status_code == 401


def test_pending_session_expires(add_client, enroll, login, client, db):
    add_client()
    authenticator = enroll()
    body = start_login(login)

    async def expire(session):
        await session.execute(
            update(Session)
            .where(Session.id == body["session_id"])
            .values(expires_at=utcnow() - timedelta(seconds=1))
        )

    db.run(expire)

    response = finish_login(client, body, authenticator.login(body["webauthn_options"]))
    assert response.status_code == 401


# --- Gestion des appareils --------------------------------------------------------


def passkey_session(client, login, authenticator):
    body = start_login(login)
    token = finish_login(client, body, authenticator.login(body["webauthn_options"])).json()
    return bearer(token["access_token"])


def test_second_device_can_be_added_from_a_passkey_session(add_client, enroll, login, client):
    add_client()
    phone = enroll()
    headers = passkey_session(client, login, phone)
    laptop = SoftAuthenticator()

    options = client.post("/passkeys/register/options", headers=headers).json()
    assert [c["id"] for c in options["excludeCredentials"]] == [phone.id]
    response = client.post(
        "/passkeys/register",
        json={"credential": laptop.register(options), "device_name": "PC Windows Hello"},
        headers=headers,
    )

    assert response.status_code == 201
    names = [p["device_name"] for p in client.get("/passkeys", headers=headers).json()]
    assert sorted(names) == ["PC Windows Hello", "iPhone de test"]


def test_registration_options_are_single_use(add_client, enroll, login, client):
    add_client()
    phone = enroll()
    headers = passkey_session(client, login, phone)
    options = client.post("/passkeys/register/options", headers=headers).json()
    credential = SoftAuthenticator().register(options)

    assert (
        client.post(
            "/passkeys/register", json={"credential": credential}, headers=headers
        ).status_code
        == 201
    )
    again = client.post("/passkeys/register", json={"credential": credential}, headers=headers)
    assert again.status_code == 409


def test_delete_a_device(add_client, enroll, login, client):
    add_client()
    phone = enroll()
    headers = passkey_session(client, login, phone)
    passkey_id = client.get("/passkeys", headers=headers).json()[0]["id"]

    assert client.delete(f"/passkeys/{passkey_id}", headers=headers).status_code == 204
    assert client.get("/passkeys", headers=headers).json() == []
    assert client.delete(f"/passkeys/{passkey_id}", headers=headers).status_code == 404


# --- Sonde (application de type service) -------------------------------------------

PROBE_KEY = "orbe_sk_probe_test"


@pytest.fixture
def probe_api(db):
    return db.add(
        ClientApi(
            id="orbe-probe",
            name="Sonde",
            type="service",
            key_hash=hash_api_key(PROBE_KEY),
            scopes=["payments", "probe"],
        )
    )


def test_probe_logs_in_without_a_passkey(probe_api, add_client, login, private_key):
    add_client(email="probe@orbe.test", is_probe=True)

    response = login(
        email="probe@orbe.test", headers={"X-Client-Id": "orbe-probe", "X-API-Key": PROBE_KEY}
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["mfa_required"], body["passkey_enrollment_required"]) == (False, False)
    claims = jwt.decode(
        body["token"]["access_token"],
        private_key.public_key(),
        algorithms=["RS256"],
        audience="orbe",
    )
    assert (claims["cid"], claims["cty"], claims["amr"]) == ("orbe-probe", "service", ["pwd"])


def test_probe_key_cannot_open_a_regular_account(probe_api, add_client, login):
    add_client()

    response = login(headers={"X-Client-Id": "orbe-probe", "X-API-Key": PROBE_KEY})

    assert response.status_code == 403


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Client-Id": "orbe-probe"},
        {"X-Client-Id": "orbe-probe", "X-API-Key": "mauvaise-cle"},
        {"X-Client-Id": "application-inconnue"},
    ],
)
def test_unknown_client_or_wrong_key_is_rejected(probe_api, add_client, login, headers):
    add_client(email="probe@orbe.test", is_probe=True)

    response = login(email="probe@orbe.test", headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_client"
