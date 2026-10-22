import pytest
from conftest import bearer

OPERATOR_ID = "11111111-2222-3333-4444-555555555555"


@pytest.mark.parametrize(
    ("method", "path", "body", "upstream"),
    [
        ("GET", "", None, "/operators/accounts"),
        (
            "POST",
            "",
            {"email": "x@orbe.test", "display_name": "X Y", "role": "viewer", "password": "p"},
            "/operators/accounts",
        ),
        ("PATCH", f"/{OPERATOR_ID}", {"role": "operator"}, f"/operators/accounts/{OPERATOR_ID}"),
        ("POST", f"/{OPERATOR_ID}/unlock", None, f"/operators/accounts/{OPERATOR_ID}/unlock"),
        (
            "POST",
            f"/{OPERATOR_ID}/face",
            {"consent": True, "frames": ["aW1n"] * 16},
            f"/operators/accounts/{OPERATOR_ID}/face",
        ),
        ("DELETE", f"/{OPERATOR_ID}/face", None, f"/operators/accounts/{OPERATOR_ID}/face"),
    ],
)
def test_admin_routes_are_relayed_with_the_admin_token(client, auth, method, path, body, upstream):
    headers = bearer(auth.token("admin@orbe.test"))

    response = client.request(method, f"/bo/admin/operators{path}", json=body, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["path"] == upstream
    assert auth.calls[-1][3]["authorization"] == headers["Authorization"]


def test_revoke_sessions_returns_204(client, auth):
    response = client.delete(
        f"/bo/admin/operators/{OPERATOR_ID}/sessions",
        headers=bearer(auth.token("admin@orbe.test")),
    )

    assert response.status_code == 204


@pytest.mark.parametrize("email", ["ops@orbe.test", "viewer@orbe.test"])
def test_admin_routes_are_refused_before_relaying_for_other_roles(client, auth, email):
    response = client.get("/bo/admin/operators", headers=bearer(auth.token(email)))

    assert response.status_code == 403
    assert not any(path.startswith("/operators/accounts") for _, path, _, _ in auth.calls)


def test_operator_id_is_validated(client, auth):
    response = client.get(
        "/bo/admin/operators/..%2F..%2Fme/face", headers=bearer(auth.token("admin@orbe.test"))
    )

    assert response.status_code in (404, 405, 422)
