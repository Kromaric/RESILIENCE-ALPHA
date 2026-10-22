import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def temp_blocklist(tmp_path):
    blocklist_file = tmp_path / "blocklist.conf"
    blocklist_file.write_text("# initial\n", encoding="utf-8")
    return blocklist_file


@pytest.fixture
def client(temp_blocklist):
    settings = Settings(
        blocklist_path=temp_blocklist,
        docker_socket="/nonexistent/docker.sock",  # Test offline / sans docker actif
        payment_url="http://mock-payment",
        cooldown_seconds=1,
    )
    app = create_app(settings)
    with TestClient(app) as tc:
        yield tc, temp_blocklist


def test_health(client):
    tc, _ = client
    res = tc.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "remediation-engine"}


def test_initial_status(client):
    tc, _ = client
    res = tc.get("/status")
    assert res.status_code == 200
    body = res.json()
    assert body["platform"] == "operational"
    assert body["payments_enabled"] is True

    pub = tc.get("/status/public").json()
    assert pub["platform"] == "operational"
    assert pub["payments_enabled"] is True


def test_trigger_manual_and_blocklist(client):
    tc, blocklist = client
    # Déclenchement manuel avec une IP attaquante forcée
    res = tc.post("/trigger?target=payment-service&forced_ip=192.168.137.50")
    assert res.status_code == 202

    # L'IP doit avoir été immédiatement écrite dans la blocklist
    content = blocklist.read_text(encoding="utf-8")
    assert "192.168.137.50 1;" in content

    # Vérification de l'historique des incidents
    incidents = tc.get("/incidents").json()
    assert len(incidents) >= 1
    inc = incidents[0]
    assert inc["target"] == "payment-service"
    assert "192.168.137.50" in inc["blocked_ips"]
    assert any(step["phase"] == "containing" for step in inc["steps"])


def test_webhook_alert(client):
    tc, _ = client
    payload = {
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "PaymentAnomaly",
                    "severity": "critical",
                    "incident_type": "resource_exhaustion",
                    "target": "payment-service",
                },
                "annotations": {
                    "summary": "Score d'anomalie élevé",
                },
            }
        ],
    }
    res = tc.post("/webhook/alert", json=payload)
    assert res.status_code == 202
