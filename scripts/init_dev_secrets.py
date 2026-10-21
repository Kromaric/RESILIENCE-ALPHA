"""Génère les secrets de l'environnement de développement local (dossier secrets/, ignoré par Git).

    services/auth-service/.venv/Scripts/python scripts/init_dev_secrets.py

Ne remplace jamais un secret existant : supprimez le fichier pour le régénérer (et recréez
alors le volume MariaDB, les mots de passe n'étant appliqués qu'au premier démarrage).
"""

import secrets
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

SECRETS = Path(__file__).resolve().parent.parent / "secrets"

PASSWORDS = [
    "db_root_password",
    "auth_db_password",
    "payment_db_password",
    "remediation_db_password",
    "exporter_db_password",
    "bo_db_password",
]


def write_once(name: str, content: bytes) -> None:
    path = SECRETS / name
    if path.exists():
        print(f"  conservé   {name}")
        return
    path.write_bytes(content)
    print(f"  créé       {name}")


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # accents corrects dans la console Windows
    SECRETS.mkdir(exist_ok=True)
    print(f"Secrets dans {SECRETS}")
    for name in PASSWORDS:
        write_once(name, secrets.token_hex(24).encode())
    write_once("probe_api_key", f"orbe_sk_probe_{secrets.token_hex(16)}".encode())
    # Clé AES-256 qui chiffre les gabarits de visage (perdue = visages à réenregistrer)
    write_once("face_embedding_key", secrets.token_hex(32).encode())

    if not (SECRETS / "jwt_private_key.pem").exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
        write_once(
            "jwt_private_key.pem",
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        )
        write_once(
            "jwt_public_key.pem",
            key.public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            ),
        )
    else:
        print("  conservé   jwt_private_key.pem / jwt_public_key.pem")


if __name__ == "__main__":
    main()
