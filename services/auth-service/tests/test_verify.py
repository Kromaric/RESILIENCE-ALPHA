import pytest

from app.models import ApiKey
from app.security import hash_api_key

KEY = "orbe_sk_test_4f9c2b7e1a"


@pytest.fixture
def api_key(db):
    return db.add(
        ApiKey(partner_name="Boutique Démo", key_hash=hash_api_key(KEY), scopes=["payments:write"])
    )


def test_verify_accepts_a_valid_key(api_key, client):
    response = client.get("/verify", headers={"X-API-Key": KEY})

    assert response.status_code == 200
    assert response.json() == {"partner": "Boutique Démo", "scopes": ["payments:write"]}


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "orbe_sk_test_inconnue"}])
def test_verify_rejects_missing_or_unknown_keys(api_key, client, headers):
    response = client.get("/verify", headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "invalid_api_key"


def test_verify_rejects_an_inactive_key(db, client):
    db.add(ApiKey(partner_name="Ancien partenaire", key_hash=hash_api_key(KEY), active=False))

    assert client.get("/verify", headers={"X-API-Key": KEY}).status_code == 401
