"""Trafic légitime pour constituer les jeux de données (profils nominal / peak / offpeak).

    $env:PROFILE="nominal"; locust -f ml/locustfile.py --headless
    python ml/collect.py --label nominal --since 30m

Prérequis : auth-service avec le moteur de visage simulé (AUTH_FACE_ENGINE=fake) — chaque
utilisateur virtuel se connecte comme scripts/dev_token.py (mot de passe + « visage »).

Variables d'environnement :
    PROFILE        nominal (défaut) | peak | offpeak
    DURATION_S     durée du profil (défaut 1800)
    ORBE_AUTH_URL  défaut http://localhost:8001
    ORBE_PAY_URL   défaut http://localhost:8002 (ou https://orbe.test/api/payments via le WAF)
    ORBE_ACCOUNTS  comptes de démo, séparés par des virgules
    SPOOF_IPS      1 (défaut) : chaque utilisateur virtuel envoie un X-Real-IP propre, pour que
                   les variables « IP sources » de Loki voient une population de clients. Sans
                   effet à travers le WAF, qui réécrit l'en-tête.
"""

from __future__ import annotations

import os
import random
import sys
import uuid
from pathlib import Path

from locust import HttpUser, LoadTestShape, between, task

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from dev_token import enroll_frames, login_frames  # noqa: E402

AUTH_URL = os.getenv("ORBE_AUTH_URL", "http://localhost:8001")
PAY_URL = os.getenv("ORBE_PAY_URL", "http://localhost:8002")
ACCOUNTS = os.getenv("ORBE_ACCOUNTS", "camille@orbe.test,lea@orbe.test,hugo@orbe.test").split(",")
PHONES = {"camille@orbe.test": "+33612345678", "lea@orbe.test": "+33612345677",
          "hugo@orbe.test": "+33612345676"}
PASSWORD = os.getenv("ORBE_PASSWORD", "demo-password")
SPOOF_IPS = os.getenv("SPOOF_IPS", "1") == "1"
VERIFY_TLS = os.getenv("ORBE_VERIFY_TLS", "1") == "1"
CARD = {"number": "4242 4242 4242 4242", "exp_month": 12, "exp_year": 2030, "cvc": "123",
        "holder": "Client Locust"}


class Client(HttpUser):
    host = PAY_URL
    wait_time = between(2, 8)  # un humain qui consulte son appli

    def on_start(self) -> None:
        self.client.verify = VERIFY_TLS
        self.email = random.choice(ACCOUNTS)
        self.ip = f"10.{random.randint(20, 60)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
        self.login()

    def headers(self, **extra) -> dict:
        h = {"Authorization": f"Bearer {self.token}", **extra}
        if SPOOF_IPS:
            h["X-Real-IP"] = self.ip
        return h

    def login(self) -> None:
        auth = self.client.post(
            f"{AUTH_URL}/login", json={"email": self.email, "password": PASSWORD}, name="auth:login"
        ).json()
        if auth.get("face_enrollment_required"):
            self.client.post(
                f"{AUTH_URL}/face/enroll",
                json={"consent": True, "frames": enroll_frames(self.email)},
                headers={"Authorization": f"Bearer {auth['token']['access_token']}"},
                name="auth:enroll",
            )
            auth = self.client.post(
                f"{AUTH_URL}/login", json={"email": self.email, "password": PASSWORD},
                name="auth:login",
            ).json()
        if not auth.get("mfa_required"):
            self.token = auth["token"]["access_token"]
            return
        challenge = auth["face_challenge"]
        token = self.client.post(
            f"{AUTH_URL}/login/face",
            json={
                "session_id": auth["session_id"],
                "frames": login_frames(self.email, challenge["direction"], challenge["frames"]),
            },
            name="auth:face",
        ).json()
        self.token = token["access_token"]

    def call(self, method: str, path: str, name: str, **kwargs) -> None:
        with self.client.request(
            method, path, name=name, catch_response=True, **kwargs
        ) as response:
            if response.status_code == 401:  # jeton expiré : on se reconnecte
                response.success()
                self.login()
            elif response.status_code in (429,):  # limite de débit = comportement normal
                response.success()

    @task(6)
    def history(self) -> None:
        self.call("GET", "/transactions?limit=20", "GET /transactions", headers=self.headers())

    @task(1)
    def pay(self) -> None:
        others = [a for a in ACCOUNTS if a != self.email and a in PHONES]
        body = {
            "recipient": PHONES[random.choice(others)],
            "amount_cents": random.randint(100, 5000),
            "currency": "EUR",
            "description": "Locust",
            "card": CARD,
        }
        self.call(
            "POST", "/pay", "POST /pay", json=body,
            headers=self.headers(**{"Idempotency-Key": str(uuid.uuid4())}),
        )


class Profile(LoadTestShape):
    """nominal : charge stable · peak : montée à ×5 puis retour · offpeak : quasi vide."""

    profile = os.getenv("PROFILE", "nominal")
    duration = int(os.getenv("DURATION_S", "1800"))

    def tick(self):
        t = self.get_run_time()
        if t > self.duration:
            return None
        if self.profile == "offpeak":
            return 2, 1
        if self.profile == "peak":
            cycle = t % 600  # toutes les 10 min : 2 min de montée, 3 min de pic, descente
            if 120 <= cycle < 300:
                return 50, 5
            return 10, 5
        return 10, 2
