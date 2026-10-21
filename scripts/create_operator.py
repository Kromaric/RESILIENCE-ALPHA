"""Crée (ou met à jour) un opérateur du back-office.

    services/auth-service/.venv/Scripts/python scripts/create_operator.py ops2@orbe.test \\
        --name "Opératrice SOC" --role operator

Le mot de passe est demandé au clavier (jamais en argument : il finirait dans l'historique).
auth-service n'a pas le droit de créer d'opérateur ni de changer un rôle : le script passe
par le compte root de MariaDB, dans le conteneur (le mot de passe root ne quitte pas le
secret Docker). Options :

    --compose docker-compose.dev.yml    fichier compose (infra : infra/docker-compose.yml)
    --service mariadb                   nom du service MariaDB dans ce fichier
    --disable                           désactive le compte (ses sessions sont révoquées)
"""

import argparse
import getpass
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "auth-service"))
from app.security import PasswordVerifier, normalize_email, password_problem, valid_email  # noqa: E402


def sql_string(value: str) -> str:
    """Littéral SQL hexadécimal : aucune valeur saisie ne peut sortir de la chaîne."""
    return f"CONVERT(X'{value.encode('utf-8').hex()}' USING utf8mb4) COLLATE utf8mb4_unicode_ci"


def run_sql(args: argparse.Namespace, sql: str) -> None:
    command = [
        "docker",
        "compose",
        "-f",
        args.compose,
        "exec",
        "-T",
        args.service,
        "sh",
        "-c",
        'MYSQL_PWD="$(cat /run/secrets/db_root_password)" mariadb -uroot orbe',
    ]
    result = subprocess.run(  # noqa: S603 — commande fixe, SQL passé sur l'entrée standard
        command, input=sql, text=True, capture_output=True, cwd=ROOT
    )
    if result.returncode != 0:
        sys.exit(f"Échec MariaDB : {result.stderr.strip()}")


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # accents corrects dans la console Windows
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("email")
    parser.add_argument("--name", help="nom affiché (création)")
    parser.add_argument("--role", choices=["viewer", "operator"], default="viewer")
    parser.add_argument("--compose", default="docker-compose.dev.yml")
    parser.add_argument("--service", default="mariadb")
    parser.add_argument("--disable", action="store_true")
    args = parser.parse_args()

    email = normalize_email(args.email)
    if not valid_email(email):
        sys.exit("Adresse email invalide.")

    # Les valeurs passent toutes par sql_string (littéraux hexadécimaux) : d'où les noqa S608
    if args.disable:
        run_sql(
            args,
            f"UPDATE operators SET active = FALSE WHERE email = {sql_string(email)};\n"  # noqa: S608
            "UPDATE operator_sessions s JOIN operators o ON o.id = s.operator_id "
            "SET s.status = 'revoked', s.revoked_at = UTC_TIMESTAMP(3), "
            "s.revocation_reason = 'operator_disabled' "
            f"WHERE o.email = {sql_string(email)} AND s.status = 'active';\n",
        )
        print(f"Opérateur {email} désactivé, sessions révoquées.")
        return

    if not args.name:
        sys.exit("--name est requis.")
    password = getpass.getpass("Mot de passe (12 caractères minimum) : ")
    problem = password_problem(password, email)
    if problem:
        sys.exit(problem)
    if getpass.getpass("Confirmation : ") != password:
        sys.exit("Les deux saisies diffèrent.")

    password_hash = PasswordVerifier(1).hash(password)
    run_sql(
        args,
        "INSERT INTO operators (id, email, display_name, password_hash, role) VALUES ("  # noqa: S608
        f"{sql_string(str(uuid.uuid4()))}, {sql_string(email)}, {sql_string(args.name)}, "
        f"{sql_string(password_hash)}, {sql_string(args.role)}) "
        "ON DUPLICATE KEY UPDATE display_name = VALUES(display_name), "
        "password_hash = VALUES(password_hash), role = VALUES(role), active = TRUE, "
        "failed_logins = 0, locked_until = NULL;\n",
    )
    print(f"Opérateur {email} ({args.role}) enregistré.")


if __name__ == "__main__":
    main()
