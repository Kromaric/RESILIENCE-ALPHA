"""Génère la paire de clés RSA des JWT pour le développement local.

    python scripts/gen_jwt_keys.py

Écrit secrets/jwt_private_key.pem (auth-service) et secrets/jwt_public_key.pem
(payment-service). Le dossier secrets/ est ignoré par Git. En déploiement, la clé
privée est stockée dans Vault (CADRAGE §9.3).
"""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

SECRETS = Path(__file__).resolve().parent.parent / "secrets"


def main() -> None:
    SECRETS.mkdir(exist_ok=True)
    private_path = SECRETS / "jwt_private_key.pem"
    public_path = SECRETS / "jwt_public_key.pem"
    if private_path.exists():
        raise SystemExit(f"{private_path} existe déjà : supprimez-le pour régénérer la paire.")

    key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    private_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    print(f"Clés écrites dans {SECRETS}")


if __name__ == "__main__":
    main()
