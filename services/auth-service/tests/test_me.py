import uuid

from cryptography.hazmat.primitives.asymmetric import rsa

from app.security import TokenService


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_me_returns_the_profile_with_a_masked_phone(add_client, login, client):
    created = add_client()
    token = login().json()["access_token"]

    response = client.get("/me", headers=bearer(token))

    assert response.status_code == 200
    assert response.json() == {
        "client_id": created.id,
        "email": "camille@orbe.test",
        "phone_masked": "+33 6 •• •• •• 78",
        "display_name": "Camille Test",
    }


def test_me_requires_a_token(client):
    response = client.get("/me")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_me_rejects_an_expired_token(add_client, client, private_key):
    created = add_client()
    expired = TokenService(private_key, "orbe-auth", "orbe", ttl=-10).issue(created.id, "x")

    assert client.get("/me", headers=bearer(expired)).status_code == 401


def test_me_rejects_a_token_signed_with_another_key(add_client, client):
    created = add_client()
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = TokenService(other_key, "orbe-auth", "orbe", ttl=900).issue(created.id, "x")

    assert client.get("/me", headers=bearer(forged)).status_code == 401


def test_me_rejects_a_token_for_an_unknown_client(client, private_key):
    token = TokenService(private_key, "orbe-auth", "orbe", ttl=900).issue(str(uuid.uuid4()), "x")

    assert client.get("/me", headers=bearer(token)).status_code == 401
