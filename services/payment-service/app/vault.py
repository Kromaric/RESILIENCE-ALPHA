"""Secrets du service : Vault KV v2 d'abord, fichiers de secrets Docker en repli.

Le même module est copié dans auth-service, payment-service et bo-api.

- `VAULT_KV_PATH` absent (défaut) : seuls les fichiers `/run/secrets/…` sont lus (pile de
  développement, tests).
- `VAULT_KV_PATH` renseigné (ex. `secret/data/oorbe/config`) : le service s'authentifie
  (AppRole si `role_id` / `secret_id` sont fournis, sinon jeton), lit le chemin une fois au
  démarrage et garde les valeurs **en mémoire** (jamais écrites sur disque). Une clé absente
  ou vide dans Vault est lue dans son fichier de secret, s'il existe.
- Vault injoignable : repli sur les fichiers, avec un avertissement dans les journaux. Sans
  fichier non plus, le service refuse de démarrer.

Les valeurs ne sont jamais journalisées : seulement le nom de la clé et sa source.
"""

import logging
from pathlib import Path

import httpx

from app.logging_setup import log_event

logger = logging.getLogger("secrets")


class SecretNotFound(RuntimeError):
    pass


def _read(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    return path.read_text(encoding="utf-8").strip() or None


class SecretStore:
    def __init__(self, values: dict[str, str] | None = None, source: str | None = None) -> None:
        self._values = values or {}
        self.source = source  # chemin Vault lu, ou None

    @classmethod
    def load(
        cls,
        *,
        addr: str,
        kv_path: str | None,
        token_file: Path | None = None,
        role_id_file: Path | None = None,
        secret_id_file: Path | None = None,
        approle_mount: str = "approle",
        timeout: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> "SecretStore":
        if not kv_path:
            return cls()
        try:
            with httpx.Client(base_url=addr, timeout=timeout, transport=transport) as client:
                token = cls._login(client, token_file, role_id_file, secret_id_file, approle_mount)
                response = client.get(f"/v1/{kv_path.strip('/')}", headers={"X-Vault-Token": token})
                response.raise_for_status()
                data = response.json()["data"]["data"]
        except (httpx.HTTPError, KeyError, ValueError, SecretNotFound) as exc:
            log_event(
                logger,
                "vault_unavailable",
                level=logging.WARNING,
                path=kv_path,
                error=exc.__class__.__name__,
            )
            return cls()
        values = {k: v.strip() for k, v in data.items() if isinstance(v, str) and v.strip()}
        log_event(logger, "vault_secrets_loaded", path=kv_path, keys=sorted(values))
        return cls(values, source=kv_path)

    @staticmethod
    def _login(client, token_file, role_id_file, secret_id_file, mount) -> str:
        role_id, secret_id = _read(role_id_file), _read(secret_id_file)
        if role_id and secret_id:
            response = client.post(
                f"/v1/auth/{mount}/login", json={"role_id": role_id, "secret_id": secret_id}
            )
            response.raise_for_status()
            return response.json()["auth"]["client_token"]
        token = _read(token_file)
        if not token:
            raise SecretNotFound("ni AppRole ni jeton Vault fourni")
        return token

    def get(self, key: str, file: Path | None = None) -> str:
        """Valeur de `key` dans Vault, sinon contenu du fichier ; erreur si aucun des deux."""
        value = self._values.get(key)
        if value:
            log_event(logger, "secret_loaded", key=key, source="vault")
            return value
        value = _read(file)
        if value:
            log_event(logger, "secret_loaded", key=key, source="file")
            return value
        raise SecretNotFound(f"Secret « {key} » introuvable : ni dans Vault, ni dans {file}")
