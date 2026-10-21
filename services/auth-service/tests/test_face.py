import asyncio
import json
import logging
from datetime import timedelta

import jwt
import numpy as np
import pytest
from conftest import bearer, encode, enroll_frames, login_frames
from sqlalchemy import update

from app.db import utcnow
from app.face.cipher import CipherError, LocalCipher
from app.face.decision import decide, head_turn, same_person, select_for_enrollment
from app.face.engine import FaceObservation, fake_frame, identity_vector
from app.logging_setup import JsonFormatter
from app.models import Client, ClientApi, ClientFaceTemplate, Session
from app.security import hash_api_key

# --- Enrôlement ------------------------------------------------------------------------


def test_enrollment_stores_encrypted_templates_only(add_client, enroll, db, client, token):
    created = add_client()

    enroll("camille")

    assert db.count(ClientFaceTemplate, ClientFaceTemplate.client_id == created.id) == 5
    stored = db.run(lambda s: _first_template(s, created.id))
    assert stored.embedding_ct.startswith("local:v1:")
    assert stored.model == "fake/v1"
    assert db.get(Client, created.id).biometric_consent_at is not None


async def _first_template(session, client_id):
    from sqlalchemy import select

    return (
        (
            await session.execute(
                select(ClientFaceTemplate).where(ClientFaceTemplate.client_id == client_id)
            )
        )
        .scalars()
        .first()
    )


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"consent": False, "frames": enroll_frames("camille")}, "consent_required"),
        (
            {"consent": True, "frames": encode(fake_frame(None, n=i) for i in range(16))},
            "enrollment_failed",
        ),
        (
            {
                "consent": True,
                "frames": enroll_frames("camille", 8) + enroll_frames("intrus", 8),
            },
            "enrollment_failed",
        ),
        ({"consent": True, "frames": ["pas du base64 !"]}, "invalid_frame"),
        ({"consent": True, "frames": enroll_frames("camille", 21)}, "too_many_frames"),
    ],
)
def test_invalid_enrollments(add_client, client, token, body, code):
    add_client()

    response = client.post("/face/enroll", json=body, headers=bearer(token()))

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == code


def test_a_password_alone_cannot_replace_or_erase_an_enrolled_face(
    add_client, enroll, client, app, db
):
    created = add_client()
    enroll("camille")
    # Session « mot de passe seul » : ce qu'obtiendrait quelqu'un qui ne connaît que le mot de passe
    session = db.add(
        Session(
            id="00000000-0000-0000-0000-0000000000aa",
            client_id=created.id,
            client_api_id="orbe-web",
            status="active",
            factors="pwd",
            expires_at=utcnow() + timedelta(minutes=5),
        )
    )
    headers = bearer(app.state.tokens.issue(created.id, created.email, session_id=session.id))

    replace = client.post(
        "/face/enroll", json={"consent": True, "frames": enroll_frames("intrus")}, headers=headers
    )
    erase = client.delete("/face", headers=headers)

    assert replace.status_code == erase.status_code == 403
    assert replace.json()["detail"]["code"] == "face_confirmation_required"


def test_erase_face_from_a_face_session(add_client, enroll, face_login, client, db):
    created = add_client()
    enroll("camille")
    _, response = face_login("camille")
    headers = bearer(response.json()["access_token"])

    assert client.delete("/face", headers=headers).status_code == 204
    assert db.count(ClientFaceTemplate, ClientFaceTemplate.client_id == created.id) == 0
    assert db.get(Client, created.id).biometric_consent_at is None
    assert client.get("/face", headers=headers).json()["enrolled"] is False


# --- Connexion -------------------------------------------------------------------------


def test_login_with_the_face(add_client, enroll, face_login, private_key, db, client):
    created = add_client()
    enroll("camille")

    step1, response = face_login("camille")

    assert step1["token"] is None
    assert step1["face_challenge"]["direction"] in ("left", "right")
    assert (step1["face_challenge"]["frames"], step1["face_challenge"]["interval_ms"]) == (12, 300)
    assert response.status_code == 200, response.text
    token = response.json()
    assert token["factors"] == ["pwd", "face"]
    claims = jwt.decode(
        token["access_token"], private_key.public_key(), algorithms=["RS256"], audience="orbe"
    )
    assert claims["amr"] == ["pwd", "face"]
    session = db.get(Session, step1["session_id"])
    assert (session.status, session.challenge) == ("active", None)
    assert session.face_template_id is not None
    assert float(session.face_score) > 0.9
    me = client.get("/me", headers=bearer(token["access_token"])).json()
    assert (me["client_id"], me["factors"], me["face_enrolled"]) == (
        created.id,
        ["pwd", "face"],
        True,
    )


def test_another_face_is_refused(add_client, enroll, face_login, db):
    created = add_client()
    enroll("camille")

    step1, response = face_login("intrus")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "second_factor_failed"
    assert db.get(Session, step1["session_id"]).status == "revoked"
    assert db.get(Client, created.id).failed_logins == 1


@pytest.mark.parametrize(
    "frames_for",
    [
        # tête tournée dans le mauvais sens
        lambda d: login_frames("camille", "right" if d == "left" else "left"),
        # photo : la tête ne bouge pas
        lambda d: encode(fake_frame("camille", yaw=5, n=i) for i in range(8)),
        # aucun visage
        lambda d: encode(fake_frame(None, n=i) for i in range(8)),
    ],
    ids=["wrong_direction", "still_photo", "no_face"],
)
def test_liveness_failures(add_client, enroll, login, client, frames_for):
    add_client()
    enroll("camille")
    step1 = login().json()

    response = client.post(
        "/login/face",
        json={
            "session_id": step1["session_id"],
            "frames": frames_for(step1["face_challenge"]["direction"]),
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "liveness_failed"


def test_a_failed_attempt_closes_the_session(add_client, enroll, face_login, client):
    add_client()
    enroll("camille")
    step1, first = face_login("intrus")

    retry = client.post(
        "/login/face",
        json={
            "session_id": step1["session_id"],
            "frames": login_frames("camille", step1["face_challenge"]["direction"]),
        },
    )

    assert (first.status_code, retry.status_code) == (401, 401)


def test_a_successful_session_cannot_be_replayed(add_client, enroll, face_login, client):
    add_client()
    enroll("camille")
    step1, first = face_login("camille")

    replay = client.post(
        "/login/face",
        json={
            "session_id": step1["session_id"],
            "frames": login_frames("camille", step1["face_challenge"]["direction"]),
        },
    )

    assert (first.status_code, replay.status_code) == (200, 401)


def test_face_failures_lock_the_account(add_client, enroll, face_login, login):
    add_client()
    enroll("camille")

    for _ in range(5):
        assert face_login("intrus")[1].status_code == 401

    assert login().status_code == 423


def test_pending_face_step_expires(add_client, enroll, login, client, db):
    add_client()
    enroll("camille")
    step1 = login().json()

    async def expire(session):
        await session.execute(
            update(Session)
            .where(Session.id == step1["session_id"])
            .values(expires_at=utcnow() - timedelta(seconds=1))
        )

    db.run(expire)
    response = client.post(
        "/login/face",
        json={
            "session_id": step1["session_id"],
            "frames": login_frames("camille", step1["face_challenge"]["direction"]),
        },
    )

    assert response.status_code == 401


def test_probe_service_cannot_enroll(db, add_client, login, client):
    db.add(
        ClientApi(
            id="orbe-probe",
            name="Sonde",
            type="service",
            key_hash=hash_api_key("cle-de-la-sonde"),
            scopes=["payments"],
        )
    )
    add_client(email="probe@orbe.test", phone="+33600000001", is_probe=True)
    token = login(
        email="probe@orbe.test",
        headers={"X-Client-Id": "orbe-probe", "X-API-Key": "cle-de-la-sonde"},
    ).json()["token"]["access_token"]

    response = client.post(
        "/face/enroll",
        json={"consent": True, "frames": enroll_frames("sonde")},
        headers=bearer(token),
    )

    assert response.status_code == 403


def test_frames_and_embeddings_are_never_logged(add_client, enroll, face_login, caplog):
    add_client()
    enroll("camille")

    with caplog.at_level(logging.INFO):
        face_login("camille")

    lines = [JsonFormatter().format(record) for record in caplog.records]
    assert any(json.loads(line)["msg"] == "login_succeeded" for line in lines)
    assert all("identity" not in line and "embedding" not in line for line in lines)


# --- Décision et chiffrement (fonctions pures) ------------------------------------------


def observation(identity, yaw=0.0, quality=0.9):
    return FaceObservation(identity_vector(identity), quality, yaw, 1.0)


def test_head_turn_is_measured_from_the_starting_position():
    assert head_turn([0, 0, 5, 10, 20, 20]) == (pytest.approx(20), 0)
    assert head_turn([10, 10, 10]) == (0, 0)
    # tourner puis revenir face à la caméra : l'amplitude atteinte compte
    assert head_turn([0, 0, 8, 15, 15, 6, 0])[0] == pytest.approx(15)
    # un pic isolé (bruit de mesure) ne suffit pas
    assert head_turn([0, 0, 1, 30, 1, 0])[0] == pytest.approx(1)
    # le sens demandé inverse les signes
    assert head_turn([0, 0, -10, -20, -20], expected_sign=-1) == (pytest.approx(20), 0)


@pytest.mark.parametrize(
    ("direction", "left_is_positive", "yaws", "expected"),
    [
        ("left", True, [0, 5, 10, 15, 20, 20], None),
        ("left", False, [0, 5, 10, 15, 20, 20], "liveness_failed"),
        ("right", False, [0, 5, 10, 15, 20, 20], None),
        ("right", True, [0, -5, -10, -15, -20, -20], None),
        # aller-retour du bon côté
        ("left", True, [0, 0, 6, 12, 14, 10, 4, 0], None),
        # balayage des deux côtés, plus ample du mauvais côté : refusé
        ("left", True, [0, 0, 10, 12, 0, -15, -20, -20], "liveness_failed"),
        # rotation trop faible
        ("left", True, [0, 0, 2, 4, 5, 5], "liveness_failed"),
    ],
)
def test_decide_checks_the_requested_direction(direction, left_is_positive, yaws, expected):
    faces = [observation("camille", yaw) for yaw in yaws]

    decision = decide(
        faces,
        [("t1", identity_vector("camille"))],
        direction=direction,
        threshold=0.4,
        min_matching_frames=3,
        min_turn_degrees=8,
        left_is_positive_yaw=left_is_positive,
    )

    assert decision.reason == expected
    assert decision.recognized is (expected is None)


def test_selection_keeps_varied_angles_and_single_faces():
    per_frame = [[observation("camille", yaw)] for yaw in range(-30, 31, 5)]
    per_frame.append([observation("camille"), observation("autre")])  # deux visages : écarté
    per_frame.append([observation("camille", quality=0.2)])  # flou : écarté

    selected = select_for_enrollment(per_frame, count=5, min_quality=0.6)

    assert [o.yaw for o in selected] == [-30, -15, 0, 15, 30]
    assert same_person(selected, 0.4)
    assert not same_person([observation("camille"), observation("autre")], 0.4)


def test_ciphertext_is_bound_to_its_owner():
    cipher = LocalCipher(bytes(32))
    vector = identity_vector("camille")

    sealed = asyncio.run(cipher.encrypt(vector, "client-a"))

    assert np.allclose(asyncio.run(cipher.decrypt(sealed, "client-a")), vector)
    with pytest.raises(CipherError):
        asyncio.run(cipher.decrypt(sealed, "client-b"))


# --- Vérification au paiement (POST /face/verify) -----------------------------------------------


def test_payment_verification_uses_the_server_challenge(add_client, enroll, face_login, client):
    add_client()
    enroll("camille")
    _, logged = face_login("camille")
    headers = bearer(logged.json()["access_token"])

    challenge = client.get("/face/challenge", headers=headers).json()
    opposite = "right" if challenge["direction"] == "left" else "left"
    # le client annonce le sens qui l'arrange et tourne de ce côté : refusé
    cheat = client.post(
        "/face/verify",
        json={"frames": login_frames("camille", opposite), "direction": opposite},
        headers=headers,
    )
    challenge = client.get("/face/challenge", headers=headers).json()
    honest = client.post(
        "/face/verify",
        json={"frames": login_frames("camille", challenge["direction"])},
        headers=headers,
    )
    replay = client.post(
        "/face/verify",
        json={"frames": login_frames("camille", challenge["direction"])},
        headers=headers,
    )

    assert cheat.status_code == 401 and cheat.json()["detail"]["code"] == "liveness_failed"
    assert honest.status_code == 200, honest.text
    assert replay.status_code == 401
    assert replay.json()["detail"]["code"] == "challenge_required"


def test_payment_verification_failures_lock_the_account(add_client, enroll, face_login, client, db):
    created = add_client()
    enroll("camille")
    _, logged = face_login("camille")
    headers = bearer(logged.json()["access_token"])

    for _ in range(2):
        challenge = client.get("/face/challenge", headers=headers).json()
        client.post(
            "/face/verify",
            json={"frames": login_frames("intrus", challenge["direction"])},
            headers=headers,
        )

    assert db.get(Client, created.id).failed_logins == 2
