import pytest

from app.models import ClientApi
from app.security import hash_api_key

KEY = "orbe_sk_test_4f9c2b7e1a"


@pytest.fixture
def partner(db):
    return db.add(
        ClientApi(
            id="demo-merchant-02",
            name="Boutique Démo",
            type="partner",
            key_hash=hash_api_key(KEY),
            scopes=["payments:read"],
        )
    )


def test_verify_accepts_a_valid_key(partner, client):
    response = client.get("/verify", headers={"X-API-Key": KEY})

    assert response.status_code == 200
    assert response.json() == {"partner": "Boutique Démo", "scopes": ["payments:read"]}


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "orbe_sk_test_inconnue"}])
def test_verify_rejects_missing_or_unknown_keys(partner, client, headers):
    response = client.get("/verify", headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_api_key"


def test_verify_rejects_an_inactive_key(db, client):
    db.add(
        ClientApi(
            id="old",
            name="Ancien partenaire",
            type="partner",
            key_hash=hash_api_key(KEY),
            active=False,
        )
    )

    assert client.get("/verify", headers={"X-API-Key": KEY}).status_code == 401


def test_partners_cannot_open_user_sessions(partner, add_client, login):
    add_client()

    response = login(headers={"X-Client-Id": "demo-merchant-02", "X-API-Key": KEY})

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "client_not_allowed"
