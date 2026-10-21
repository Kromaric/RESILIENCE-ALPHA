import pytest
from conftest import bearer
from fastapi import Depends

from app.security import Operator, require_role

SESSION = "00000000-0000-0000-0000-000000000001"


def test_login_steps_are_relayed_in_order_with_the_operator_ip(client, auth):
    ip = {"X-Real-IP": "192.168.137.20"}

    step1 = client.post("/bo/auth/identify", json={"email": "ops@orbe.test"}, headers=ip)
    step2 = client.post(
        "/bo/auth/face", json={"session_id": SESSION, "frames": ["aW1n"] * 12}, headers=ip
    )
    step3 = client.post(
        "/bo/auth/password", json={"session_id": SESSION, "password": "demo-password"}, headers=ip
    )

    assert step1.json()["step"] == "face" and step1.json()["face_challenge"]["frames"] == 12
    assert step2.json()["step"] == "password"
    assert step3.status_code == 200 and step3.json()["role"] == "operator"
    paths = [path for _, path, _, _ in auth.calls]
    assert paths == [
        "/operators/login/identify",
        "/operators/login/face",
        "/operators/login/password",
    ]
    assert all(headers["x-real-ip"] == "192.168.137.20" for *_, headers in auth.calls)


def test_identification_lock_is_passed_through_with_retry_after(client, auth):
    auth.replies["/operators/login/identify"] = (
        429,
        {"detail": {"code": "identification_locked", "message": "Attendez."}},
        {"Retry-After": "27"},
    )

    response = client.post("/bo/auth/identify", json={"email": "ops@orbe.test"})

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "27"
    assert response.json()["detail"]["code"] == "identification_locked"


def test_wrong_password_is_passed_through(client):
    response = client.post("/bo/auth/password", json={"session_id": SESSION, "password": "mauvais"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_credentials"


def test_validation_errors_never_echo_the_password(client):
    response = client.post("/bo/auth/password", json={"session_id": SESSION, "password": ""})

    assert response.status_code == 422
    assert "input" not in response.text


def test_bootstrap_enrollment_is_relayed_with_its_token(client, auth):
    auth.replies["/operators/me/face"] = (201, {"enrolled": True, "templates": 5}, {})

    response = client.post(
        "/bo/auth/enroll-face",
        json={"consent": True, "frames": ["aW1n"] * 16},
        headers=bearer("jeton-d-enrolement"),
    )

    assert response.status_code == 201
    assert auth.calls[-1][3]["authorization"] == "Bearer jeton-d-enrolement"


def test_me_returns_the_operator(client, auth):
    token = auth.token("viewer@orbe.test")

    response = client.get("/bo/auth/me", headers=bearer(token))

    assert response.status_code == 200
    assert (response.json()["email"], response.json()["role"]) == ("viewer@orbe.test", "viewer")


@pytest.mark.parametrize(
    "make_token",
    [
        lambda auth: None,
        lambda auth: "pas-un-jwt",
        lambda auth: auth.token(audience="orbe"),  # jeton client
        lambda auth: auth.token(typ="client"),
        lambda auth: auth.token(ttl=-10),  # expiré
    ],
    ids=["missing", "garbage", "client_audience", "not_operator", "expired"],
)
def test_invalid_tokens_are_refused_without_calling_auth(client, auth, make_token):
    token = make_token(auth)
    headers = bearer(token) if token else {}

    response = client.get("/bo/auth/me", headers=headers)

    assert response.status_code == 401
    assert auth.me_calls == 0


def test_session_check_is_cached(client, auth):
    headers = bearer(auth.token())

    for _ in range(5):
        assert client.get("/bo/auth/me", headers=headers).status_code == 200

    assert auth.me_calls == 1


def test_logout_revokes_the_session_immediately(client, auth):
    headers = bearer(auth.token())
    assert client.get("/bo/auth/me", headers=headers).status_code == 200

    assert client.post("/bo/auth/logout", headers=headers).status_code == 204
    assert client.get("/bo/auth/me", headers=headers).status_code == 401


def test_session_revoked_in_auth_service_is_refused(client, auth):
    token = auth.token()
    auth.sessions.clear()  # session révoquée (compte désactivé, déconnexion ailleurs…)

    assert client.get("/bo/auth/me", headers=bearer(token)).status_code == 401


def test_auth_service_down_gives_503(client, auth):
    token = auth.token()
    auth.down = True

    response = client.get("/bo/auth/me", headers=bearer(token))
    login = client.post("/bo/auth/identify", json={"email": "ops@orbe.test"})

    assert (response.status_code, login.status_code) == (503, 503)
    assert response.json()["detail"]["code"] == "auth_unavailable"


def test_roles_are_ordered(app, client, auth):
    @app.get("/test/operator-only")
    async def operator_only(operator: Operator = Depends(require_role("operator"))):
        return {"ok": True}

    viewer = client.get("/test/operator-only", headers=bearer(auth.token("viewer@orbe.test")))
    operator = client.get("/test/operator-only", headers=bearer(auth.token("ops@orbe.test")))

    assert (viewer.status_code, operator.status_code) == (403, 200)


def test_health_and_metrics(client):
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").status_code == 200
    assert "bo_upstream_errors_total" in client.get("/metrics").text
