"""Connexion au back-office (identifiant → visage → mot de passe), LED et habilitations."""

import logging
from datetime import timedelta

import jwt
import pytest
from conftest import DEVICE_KEY, PASSWORD, bearer, encode, login_frames
from sqlalchemy import update

from app.db import utcnow
from app.face.engine import fake_frame
from app.led import LedController
from app.models import Operator, OperatorFaceTemplate, OperatorSession


def identify(client, email="ops@orbe.test"):
    return client.post("/operators/login/identify", json={"email": email})


def face(client, step, identity="ops", direction=None):
    direction = direction or step["face_challenge"]["direction"]
    return client.post(
        "/operators/login/face",
        json={"session_id": step["session_id"], "frames": login_frames(identity, direction)},
    )


def password(client, session_id, value=PASSWORD):
    return client.post(
        "/operators/login/password", json={"session_id": session_id, "password": value}
    )


def led(client):
    response = client.get("/devices/led", headers={"X-Device-Key": DEVICE_KEY})
    assert response.status_code == 200
    return response.json()


@pytest.fixture
def operator(add_operator, enroll_operator):
    def _create(email="ops@orbe.test", role="operator", identity="ops", **fields):
        created = add_operator(email=email, role=role, **fields)
        enroll_operator(created.id, identity)
        return created

    return _create


@pytest.fixture
def admin_headers(client, operator):
    """Session d'administrateur ouverte avec visage + mot de passe."""
    operator(email="admin@orbe.test", role="admin", identity="admin")
    step = identify(client, "admin@orbe.test").json()
    face(client, step, "admin")
    return bearer(password(client, step["session_id"]).json()["access_token"])


# --- Parcours nominal --------------------------------------------------------------------------


def test_identifier_then_face_then_password(client, operator, private_key, db):
    created = operator()
    assert led(client)["state"] == "off"

    step = identify(client)
    assert step.status_code == 200, step.text
    step = step.json()
    assert step["step"] == "face" and step["face_challenge"]["direction"] in ("left", "right")

    after_face = face(client, step)
    assert after_face.status_code == 200, after_face.text
    assert after_face.json()["step"] == "password"
    assert led(client)["state"] == "green_blink"

    token = password(client, step["session_id"])
    assert token.status_code == 200, token.text
    assert led(client)["state"] == "green_fixed"
    assert led(client)["remaining_ms"] > 25_000
    claims = jwt.decode(
        token.json()["access_token"],
        private_key.public_key(),
        algorithms=["RS256"],
        audience="orbe-bo",
    )
    assert (claims["sub"], claims["role"]) == (created.id, "operator")
    me = client.get("/operators/me", headers=bearer(token.json()["access_token"])).json()
    assert me["factors"] == ["face", "pwd"]
    session = db.get(OperatorSession, step["session_id"])
    assert (session.status, session.face_template_id is not None) == ("active", True)


def test_password_cannot_be_sent_before_the_face(client, operator):
    operator()
    step = identify(client).json()

    assert password(client, step["session_id"]).status_code == 401


# --- Échecs : visage -----------------------------------------------------------------------------


def test_unknown_identifier_fails_at_the_face_without_revealing_it(client, operator):
    operator()

    known, unknown = identify(client).json(), identify(client, "personne@orbe.test").json()

    assert set(known) == set(unknown) and unknown["step"] == "face"
    response = face(client, unknown, "personne")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "face_not_recognized"


def test_face_not_recognized_turns_led_red_and_locks_identification(client, operator, db):
    created = operator()
    step = identify(client).json()

    response = face(client, step, identity="intrus")

    assert response.status_code == 401
    assert led(client)["state"] == "red_fixed"
    assert 29_000 < led(client)["remaining_ms"] <= 30_000
    locked = identify(client)
    assert locked.status_code == 429
    assert locked.json()["detail"]["code"] == "identification_locked"
    assert 1 <= int(locked.headers["Retry-After"]) <= 30
    assert db.get(Operator, created.id).failed_logins == 1
    assert db.get(OperatorSession, step["session_id"]).status == "revoked"


def test_still_photo_fails_liveness(client, operator):
    operator()
    step = identify(client).json()

    response = client.post(
        "/operators/login/face",
        json={
            "session_id": step["session_id"],
            "frames": encode(fake_frame("ops", yaw=5, n=i) for i in range(12)),
        },
    )

    assert response.json()["detail"]["code"] == "liveness_failed"
    assert led(client)["state"] == "red_fixed"


def test_identification_is_free_again_after_30_seconds(app, client, operator):
    now = [1000.0]
    app.state.led = LedController(500, clock=lambda: now[0])
    operator()
    face(client, identify(client).json(), identity="intrus")

    now[0] += 29
    assert identify(client).status_code == 429
    now[0] += 2
    assert identify(client).status_code == 200
    assert led(client)["state"] == "off"


# --- Échecs : mot de passe -----------------------------------------------------------------------


def test_wrong_password_blinks_red_ten_times_and_restarts(client, operator):
    operator()
    step = identify(client).json()
    face(client, step)

    wrong = password(client, step["session_id"], "mauvais-mot-de-passe")

    assert wrong.status_code == 401
    state = led(client)
    assert (state["state"], state["blinks"], state["blink_period_ms"]) == ("red_blink", 10, 500)
    assert password(client, step["session_id"]).status_code == 401  # session close
    assert identify(client).status_code == 200  # on recommence à l'identifiant


def test_led_red_blink_ends_after_the_ten_blinks(app, client, operator):
    now = [1000.0]
    app.state.led = LedController(500, clock=lambda: now[0])
    operator()
    step = identify(client).json()
    face(client, step)
    password(client, step["session_id"], "mauvais-mot-de-passe")
    seq = led(client)["seq"]

    now[0] += 5.1

    assert led(client)["state"] == "off"
    assert led(client)["seq"] > seq


def test_failures_lock_the_operator(client, operator):
    operator()
    for _ in range(5):
        step = identify(client).json()
        face(client, step)
        password(client, step["session_id"], "mauvais-mot-de-passe")

    response = identify(client)

    assert response.status_code == 423


def test_pending_step_expires(client, operator, db):
    operator()
    step = identify(client).json()

    async def expire(session):
        await session.execute(
            update(OperatorSession)
            .where(OperatorSession.id == step["session_id"])
            .values(expires_at=utcnow() - timedelta(seconds=1))
        )

    db.run(expire)

    assert face(client, step).json()["detail"]["code"] == "login_step_expired"


def test_disabled_operator_cannot_log_in(client, operator):
    operator(active=False)
    step = identify(client).json()

    assert face(client, step).status_code == 401


# --- LED : accès de l'ESP8266 --------------------------------------------------------------------


@pytest.mark.parametrize("key", [None, "mauvaise-cle"])
def test_led_requires_the_device_key(client, key):
    headers = {"X-Device-Key": key} if key else {}

    response = client.get("/devices/led", headers=headers)

    assert response.status_code == 401


# --- Démarrage : premier opérateur sans visage ----------------------------------------------------


def test_first_operator_enrolls_own_face_then_logs_in_with_it(client, add_operator, db):
    created = add_operator(email="admin@orbe.test", role="admin")

    step = identify(client, "admin@orbe.test").json()
    assert (step["step"], step["face_enrollment_required"]) == ("password", True)
    token = password(client, step["session_id"]).json()
    assert token["face_enrollment_required"] is True
    headers = bearer(token["access_token"])
    assert client.get("/operators/me", headers=headers).status_code == 401  # jeton limité

    frames = encode(fake_frame("admin", yaw=-30 + 4 * i, n=i) for i in range(16))
    enrolled = client.post(
        "/operators/me/face", json={"consent": True, "frames": frames}, headers=headers
    )
    assert enrolled.status_code == 201, enrolled.text
    assert db.count(OperatorFaceTemplate, OperatorFaceTemplate.operator_id == created.id) >= 3
    assert (
        client.post(
            "/operators/me/face", json={"consent": True, "frames": frames}, headers=headers
        ).status_code
        == 401
    )

    again = identify(client, "admin@orbe.test").json()
    assert again["step"] == "face"
    face(client, again, "admin")
    assert password(client, again["session_id"]).status_code == 200


def test_after_bootstrap_a_password_alone_never_registers_a_face(client, operator, add_operator):
    operator(email="admin@orbe.test", role="admin", identity="admin")
    add_operator(email="nouveau@orbe.test")

    step = identify(client, "nouveau@orbe.test").json()

    assert step["step"] == "face"  # pas d'enrôlement par soi-même : échec au visage
    assert face(client, step, "nouveau").status_code == 401


# --- Habilitations (admin) -----------------------------------------------------------------------


def test_admin_creates_an_operator_and_enrolls_their_face(client, admin_headers):
    created = client.post(
        "/operators/accounts",
        json={
            "email": "Lea.SOC@orbe.test",
            "display_name": "Léa  SOC",
            "role": "operator",
            "password": "un-mot-de-passe-solide",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text
    account = created.json()
    assert (account["email"], account["display_name"], account["face_enrolled"]) == (
        "lea.soc@orbe.test",
        "Léa SOC",
        False,
    )

    frames = encode(fake_frame("lea", yaw=-30 + 4 * i, n=i) for i in range(16))
    no_consent = client.post(
        f"/operators/accounts/{account['operator_id']}/face",
        json={"consent": False, "frames": frames},
        headers=admin_headers,
    )
    enrolled = client.post(
        f"/operators/accounts/{account['operator_id']}/face",
        json={"consent": True, "frames": frames},
        headers=admin_headers,
    )

    assert no_consent.status_code == 422
    assert enrolled.status_code == 201 and enrolled.json()["face_enrolled"] is True
    step = identify(client, "lea.soc@orbe.test").json()
    face(client, step, "lea")
    assert password(client, step["session_id"], "un-mot-de-passe-solide").status_code == 200


def test_admin_lists_operators(client, admin_headers, operator):
    operator()

    accounts = client.get("/operators/accounts", headers=admin_headers).json()

    assert {a["email"] for a in accounts} == {"admin@orbe.test", "ops@orbe.test"}
    assert all(a["face_enrolled"] for a in accounts)


def test_disabling_an_operator_revokes_their_sessions(client, admin_headers, operator):
    created = operator()
    step = identify(client).json()
    face(client, step)
    ops = bearer(password(client, step["session_id"]).json()["access_token"])

    response = client.patch(
        f"/operators/accounts/{created.id}", json={"active": False}, headers=admin_headers
    )

    assert response.status_code == 200 and response.json()["active"] is False
    assert client.get("/operators/me", headers=ops).status_code == 401


def test_role_change_applies_immediately(client, admin_headers, operator):
    created = operator(role="viewer")
    step = identify(client).json()
    face(client, step)
    ops = bearer(password(client, step["session_id"]).json()["access_token"])

    client.patch(
        f"/operators/accounts/{created.id}", json={"role": "operator"}, headers=admin_headers
    )

    assert client.get("/operators/me", headers=ops).json()["role"] == "operator"


def test_the_last_admin_cannot_be_removed(client, admin_headers, db):
    admin = client.get("/operators/accounts", headers=admin_headers).json()[0]

    demote = client.patch(
        f"/operators/accounts/{admin['operator_id']}",
        json={"role": "viewer"},
        headers=admin_headers,
    )
    disable = client.patch(
        f"/operators/accounts/{admin['operator_id']}", json={"active": False}, headers=admin_headers
    )

    assert demote.status_code == disable.status_code == 409


def test_password_reset_unlock_revoke_and_face_erase(client, admin_headers, operator, db):
    created = operator()
    base = f"/operators/accounts/{created.id}"

    weak = client.post(f"{base}/password", json={"password": "court"}, headers=admin_headers)
    reset = client.post(
        f"{base}/password", json={"password": "nouveau-mot-de-passe"}, headers=admin_headers
    )
    unlock = client.post(f"{base}/unlock", headers=admin_headers)
    revoke = client.delete(f"{base}/sessions", headers=admin_headers)
    erased = client.delete(f"{base}/face", headers=admin_headers)

    assert weak.status_code == 422
    assert (reset.status_code, unlock.status_code, revoke.status_code) == (204, 200, 204)
    assert erased.json()["face_enrolled"] is False
    assert db.count(OperatorFaceTemplate, OperatorFaceTemplate.operator_id == created.id) == 0


@pytest.mark.parametrize("role", ["viewer", "operator"])
def test_habilitations_are_reserved_to_admins(client, operator, role):
    operator(role=role)
    step = identify(client).json()
    face(client, step)
    headers = bearer(password(client, step["session_id"]).json()["access_token"])

    assert client.get("/operators/accounts", headers=headers).status_code == 403


def test_admin_actions_are_audited(client, admin_headers, operator, caplog):
    created = operator()

    with caplog.at_level(logging.INFO, logger="operator_admin"):
        client.post(f"/operators/accounts/{created.id}/unlock", headers=admin_headers)

    audits = [r for r in caplog.records if r.getMessage() == "operator_admin_action"]
    assert audits and audits[0].fields["action"] == "unlock"
    assert audits[0].fields["target_id"] == created.id


# --- Séparation clients / opérateurs -------------------------------------------------------------


def test_client_and_operator_tokens_are_not_interchangeable(client, operator, add_client, token):
    operator()
    add_client()
    step = identify(client).json()
    face(client, step)
    operator_token = password(client, step["session_id"]).json()["access_token"]

    assert client.get("/operators/me", headers=bearer(token())).status_code == 401
    assert client.get("/me", headers=bearer(operator_token)).status_code == 401


def test_client_face_template_cannot_open_an_operator_account(
    client, add_client, enroll, operator, db
):
    """Même visage, mais un gabarit de client ne se déchiffre pas comme gabarit d'opérateur."""
    operator()
    from app.models import ClientFaceTemplate

    add_client()
    enroll("ops")
    template = db.run(lambda s: _first(s, ClientFaceTemplate))
    op = db.run(lambda s: _first(s, Operator))

    async def copy(session):
        await session.execute(
            update(OperatorFaceTemplate)
            .where(OperatorFaceTemplate.operator_id == op.id)
            .values(embedding_ct=template.embedding_ct)
        )

    db.run(copy)
    step = identify(client).json()

    assert face(client, step).status_code == 503  # déchiffrement refusé : rien n'est reconnu


async def _first(session, model):
    from sqlalchemy import select

    return (await session.execute(select(model))).scalars().first()
