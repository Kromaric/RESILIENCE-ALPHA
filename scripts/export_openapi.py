"""Exporte la spécification OpenAPI d'un service dans docs/api/.

À lancer avec l'environnement Python du service concerné :

    services/auth-service/.venv/Scripts/python scripts/export_openapi.py auth-service
    services/payment-service/.venv/Scripts/python scripts/export_openapi.py payment-service

Produit docs/api/<service>.openapi.json, puis régénère docs/api/specs.js (lu par la page
Swagger UI docs/api/index.html, qui fonctionne aussi ouverte directement depuis le disque).
Aucune base de données ni vraie clé n'est nécessaire : l'application est construite sans
démarrer, avec une clé RSA jetable.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "api"

SERVICES = {
    "auth-service": {
        "prefix": "AUTH",
        "key_setting": "JWT_PRIVATE_KEY_FILE",
        "public": "/api/auth",
        "port": 8001,
    },
    "payment-service": {
        "prefix": "PAYMENT",
        "key_setting": "JWT_PUBLIC_KEY_FILE",
        "public": "/api/payments",
        "port": 8002,
    },
}


def write_temporary_key(directory: Path, service: str) -> Path:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path = directory / "jwt.pem"
    if SERVICES[service]["key_setting"] == "JWT_PRIVATE_KEY_FILE":
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    else:
        pem = key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    path.write_bytes(pem)
    return path


def build_spec(service: str) -> dict:
    config = SERVICES[service]
    prefix = config["prefix"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        os.environ[f"{prefix}_DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_dir / 'openapi.db'}"
        os.environ[f"{prefix}_{config['key_setting']}"] = str(write_temporary_key(tmp_dir, service))
        os.environ[f"{prefix}_ENABLE_DOCS"] = "true"
        sys.path.insert(0, str(ROOT / "services" / service))
        from app.main import create_app

        spec = create_app().openapi()

    spec["servers"] = [
        {
            "url": f"https://192.168.137.1{config['public']}",
            "description": "Démonstrateur, à travers le WAF",
        },
        {"url": f"http://localhost:{config['port']}", "description": "Service lancé en local"},
    ]
    return spec


def write_specs_js() -> None:
    specs = {
        path.name.removesuffix(".openapi.json"): json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(DOCS.glob("*.openapi.json"))
    }
    payload = json.dumps(specs, ensure_ascii=False, indent=1)
    (DOCS / "specs.js").write_text(
        "// Généré par scripts/export_openapi.py — ne pas modifier à la main.\n"
        f"window.ORBE_SPECS = {payload};\n",
        encoding="utf-8",
    )


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in SERVICES:
        raise SystemExit(f"Usage : export_openapi.py {{{'|'.join(SERVICES)}}}")
    service = sys.argv[1]
    DOCS.mkdir(parents=True, exist_ok=True)
    target = DOCS / f"{service}.openapi.json"
    spec = build_spec(service)
    target.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_specs_js()
    print(f"{target.relative_to(ROOT)} : {len(spec['paths'])} chemins")


if __name__ == "__main__":
    main()
