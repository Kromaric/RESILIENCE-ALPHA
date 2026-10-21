"""Chargeur de secrets (app/vault.py, identique dans les trois services)."""

import json
import logging

import httpx
import pytest

from app.logging_setup import JsonFormatter
from app.vault import SecretNotFound, SecretStore

PATH = "secret/data/oorbe/config"


class FakeVault:
    def __init__(self, data=None, *, token="s.service", down=False):  # noqa: S107 — jeton factice
        self.data = data if data is not None else {}
        self.token = token
        self.down = down
        self.calls: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request.url.path)
        if self.down:
            raise httpx.ConnectError("vault injoignable", request=request)
        if request.url.path == "/v1/auth/approle/login":
            body = json.loads(request.content)
            if body == {"role_id": "role", "secret_id": "secret"}:
                return httpx.Response(200, json={"auth": {"client_token": "s.approle"}})
            return httpx.Response(400, json={"errors": ["invalid role or secret ID"]})
        if request.headers.get("x-vault-token") not in (self.token, "s.approle"):
            return httpx.Response(403, json={"errors": ["permission denied"]})
        if request.url.path == f"/v1/{PATH}":
            return httpx.Response(200, json={"data": {"data": self.data, "metadata": {}}})
        return httpx.Response(404, json={"errors": []})


@pytest.fixture
def files(tmp_path):
    def write(name, content):
        path = tmp_path / name
        path.write_text(content, encoding="utf-8")
        return path

    return write


def load(vault, **kwargs):
    return SecretStore.load(
        addr="http://vault.test",
        kv_path=PATH,
        transport=httpx.MockTransport(vault.handler),
        **kwargs,
    )


def test_without_kv_path_only_files_are_read(files):
    store = SecretStore.load(addr="http://vault.test", kv_path=None)

    assert store.get("auth_db_password", files("db", "depuis-le-fichier\n")) == "depuis-le-fichier"
    assert store.source is None


def test_vault_value_wins_over_the_file(files):
    vault = FakeVault({"auth_db_password": "depuis-vault"})

    store = load(vault, token_file=files("token", "s.service"))

    assert store.get("auth_db_password", files("db", "depuis-le-fichier")) == "depuis-vault"
    assert store.source == PATH


def test_approle_is_used_when_provided(files):
    vault = FakeVault({"auth_db_password": "depuis-vault"}, token="autre")

    store = load(
        vault,
        token_file=files("token", "s.inutilise"),
        role_id_file=files("role_id", "role"),
        secret_id_file=files("secret_id", "secret"),
    )

    assert store.get("auth_db_password") == "depuis-vault"
    assert vault.calls[0] == "/v1/auth/approle/login"


@pytest.mark.parametrize("data", [{}, {"auth_db_password": ""}, {"auth_db_password": "   "}])
def test_missing_or_empty_key_falls_back_to_the_file(files, data):
    store = load(FakeVault(data), token_file=files("token", "s.service"))

    assert store.get("auth_db_password", files("db", "depuis-le-fichier")) == "depuis-le-fichier"


@pytest.mark.parametrize(
    "vault",
    [FakeVault(down=True), FakeVault(token="autre")],
    ids=["unreachable", "permission_denied"],
)
def test_vault_failure_falls_back_to_files(files, vault, caplog):
    with caplog.at_level(logging.WARNING, logger="secrets"):
        store = load(vault, token_file=files("token", "s.service"))

    assert store.get("auth_db_password", files("db", "depuis-le-fichier")) == "depuis-le-fichier"
    assert any(r.getMessage() == "vault_unavailable" for r in caplog.records)


def test_no_credentials_for_vault_falls_back_to_files(files, tmp_path):
    vault = FakeVault({"auth_db_password": "depuis-vault"})

    store = load(vault, token_file=tmp_path / "absent")

    assert vault.calls == []
    assert store.get("auth_db_password", files("db", "depuis-le-fichier")) == "depuis-le-fichier"


def test_secret_found_nowhere_stops_the_service(files, tmp_path):
    store = load(FakeVault({}), token_file=files("token", "s.service"))

    with pytest.raises(SecretNotFound, match="auth_db_password"):
        store.get("auth_db_password", tmp_path / "absent")


def test_values_are_never_logged(files, caplog):
    vault = FakeVault({"auth_db_password": "valeur-tres-secrete", "autre": "x"})

    with caplog.at_level(logging.INFO, logger="secrets"):
        store = load(vault, token_file=files("token", "s.service"))
        store.get("auth_db_password")

    lines = [JsonFormatter().format(record) for record in caplog.records]
    assert any('"source": "vault"' in line for line in lines)
    assert all("valeur-tres-secrete" not in line and "s.service" not in line for line in lines)
