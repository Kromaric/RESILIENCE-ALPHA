"""Obtient un jeton « fort » (mot de passe + passkey) pour tester l'API dans Swagger.

    services/auth-service/.venv/Scripts/python scripts/dev_token.py camille@orbe.test

Sans navigateur ni téléphone, la passkey est simulée par l'authentificateur logiciel des tests
(services/auth-service/tests/soft_authenticator.py). Sa clé est conservée dans
secrets/dev-passkeys/ pour être réutilisée aux appels suivants (développement local uniquement).

Options :
    --password demo-password    mot de passe du compte (par défaut : demo-password)
    --auth http://localhost:8001
    --probe                     se connecter en tant que sonde (clé de service, sans passkey)
"""

import argparse
import base64
import json
import sys
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import serialization

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "auth-service" / "tests"))
from soft_authenticator import SoftAuthenticator  # noqa: E402

STORE = ROOT / "secrets" / "dev-passkeys"


def load(email: str) -> SoftAuthenticator | None:
    path = STORE / f"{email}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    authenticator = SoftAuthenticator()
    authenticator.key = serialization.load_pem_private_key(data["key"].encode(), password=None)
    authenticator.credential_id = base64.b64decode(data["credential_id"])
    authenticator.sign_count = data["sign_count"]
    return authenticator


def save(email: str, authenticator: SoftAuthenticator) -> None:
    STORE.mkdir(parents=True, exist_ok=True)
    pem = authenticator.key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    data = {
        "key": pem,
        "credential_id": base64.b64encode(authenticator.credential_id).decode(),
        "sign_count": authenticator.sign_count,
    }
    (STORE / f"{email}.json").write_text(json.dumps(data))


def fail(message: str, response: httpx.Response) -> None:
    sys.exit(f"{message} : HTTP {response.status_code} {response.text}")


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # accents corrects dans la console Windows
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email")
    parser.add_argument("--password", default="demo-password")
    parser.add_argument("--auth", default="http://localhost:8001")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()

    def login() -> dict:
        headers = {}
        if args.probe:
            key = (ROOT / "secrets" / "probe_api_key").read_text().strip()
            headers = {"X-Client-Id": "orbe-probe", "X-API-Key": key}
        response = httpx.post(
            f"{args.auth}/login", json={"email": args.email, "password": args.password}, headers=headers
        )
        if response.status_code != 200:
            fail("Connexion refusée", response)
        return response.json()

    body = login()
    if body["passkey_enrollment_required"]:
        authenticator = load(args.email) or SoftAuthenticator()
        headers = {"Authorization": f"Bearer {body['token']['access_token']}"}
        options = httpx.post(f"{args.auth}/passkeys/register/options", headers=headers)
        if options.status_code != 200:
            fail("Options d'enregistrement refusées", options)
        registered = httpx.post(
            f"{args.auth}/passkeys/register",
            json={"credential": authenticator.register(options.json()), "device_name": "Passkey de dev"},
            headers=headers,
        )
        if registered.status_code != 201:
            fail("Enregistrement de la passkey refusé", registered)
        save(args.email, authenticator)
        print(f"Passkey de dev enregistrée pour {args.email}", file=sys.stderr)
        body = login()

    if body["mfa_required"]:
        authenticator = load(args.email)
        if authenticator is None:
            sys.exit(
                f"{args.email} a déjà une passkey qui n'a pas été créée par ce script : "
                "recréez la base (docker compose -f docker-compose.dev.yml down -v)."
            )
        response = httpx.post(
            f"{args.auth}/login/passkey",
            json={"session_id": body["session_id"], "credential": authenticator.login(body["webauthn_options"])},
        )
        if response.status_code != 200:
            fail("Passkey refusée", response)
        save(args.email, authenticator)
        token = response.json()
    else:
        token = body["token"]

    print(f"Facteurs : {', '.join(token['factors'])} · valable {token['expires_in'] // 60} min", file=sys.stderr)
    print(token["access_token"])


if __name__ == "__main__":
    main()
