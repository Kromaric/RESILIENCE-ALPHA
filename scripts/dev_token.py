"""Obtient un jeton « fort » (mot de passe + visage) pour tester l'API dans Swagger.

    services/auth-service/.venv/Scripts/python scripts/dev_token.py camille@orbe.test

Fonctionne avec le moteur de reconnaissance faciale simulé (AUTH_FACE_ENGINE=fake, réglage
de docker-compose.dev.yml) : les « images » envoyées décrivent le visage au lieu d'être des
photos. Au premier appel, le visage du compte est enregistré, puis la connexion passe par le
défi de vivacité (tourner la tête dans le sens demandé). Développement local uniquement.

Options :
    --password demo-password    mot de passe du compte (par défaut : demo-password)
    --auth http://localhost:8001
    --probe                     se connecter en tant que sonde (clé de service, sans visage)
    --face autre                présenter un autre visage (pour voir le refus)
"""

import argparse
import base64
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent


def frame(identity: str, yaw: float, n: int) -> str:
    """Image simulée, au format attendu par le moteur simulé d'auth-service."""
    data = {"identity": identity, "yaw": round(yaw, 1), "quality": 0.9, "n": n}
    return base64.b64encode(json.dumps(data).encode()).decode()


def enroll_frames(identity: str, count: int = 16) -> list[str]:
    """La tête balaie de −30° à +30°."""
    return [frame(identity, -30 + 60 * i / (count - 1), i) for i in range(count)]


def login_frames(identity: str, direction: str, count: int) -> list[str]:
    """La tête tourne de 0° à 20° dans le sens demandé (gauche = lacet positif)."""
    sign = 1 if direction == "left" else -1
    return [frame(identity, sign * 20 * i / (count - 1), 100 + i) for i in range(count)]


def fail(message: str, response: httpx.Response) -> None:
    sys.exit(f"{message} : HTTP {response.status_code} {response.text}")


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")  # accents corrects dans la console Windows
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("email")
    parser.add_argument("--password", default="demo-password")
    parser.add_argument("--auth", default="http://localhost:8001")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--face", help="visage présenté (par défaut : celui du compte)")
    args = parser.parse_args()
    identity = args.face or args.email

    def login() -> dict:
        headers = {}
        if args.probe:
            key = (ROOT / "secrets" / "probe_api_key").read_text().strip()
            headers = {"X-Client-Id": "orbe-probe", "X-API-Key": key}
        response = httpx.post(
            f"{args.auth}/login",
            json={"email": args.email, "password": args.password},
            headers=headers,
        )
        if response.status_code != 200:
            fail("Connexion refusée", response)
        return response.json()

    body = login()
    if body["face_enrollment_required"]:
        enrolled = httpx.post(
            f"{args.auth}/face/enroll",
            json={"consent": True, "frames": enroll_frames(args.email)},
            headers={"Authorization": f"Bearer {body['token']['access_token']}"},
        )
        if enrolled.status_code != 201:
            fail("Enregistrement du visage refusé", enrolled)
        print(f"Visage de dev enregistré pour {args.email}", file=sys.stderr)
        body = login()

    if body["mfa_required"]:
        challenge = body["face_challenge"]
        side = "gauche" if challenge["direction"] == "left" else "droite"
        print(f"Défi : tourner la tête vers la {side}", file=sys.stderr)
        response = httpx.post(
            f"{args.auth}/login/face",
            json={
                "session_id": body["session_id"],
                "frames": login_frames(identity, challenge["direction"], challenge["frames"]),
            },
        )
        if response.status_code != 200:
            fail("Visage refusé", response)
        token = response.json()
    else:
        token = body["token"]

    factors = ", ".join(token["factors"])
    print(f"Facteurs : {factors} · valable {token['expires_in'] // 60} min", file=sys.stderr)
    print(token["access_token"])


if __name__ == "__main__":
    main()
