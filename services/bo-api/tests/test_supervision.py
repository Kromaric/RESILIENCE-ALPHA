import json
import time

import pytest
from conftest import bearer

from app import fmt
from app.routes.supervision import log_line

NOMINAL = {
    "avg_over_time(up": 99.98,
    'highr_seconds_bucket{job="payment-service"}': 182.4,
    'highr_seconds_bucket{job="auth-service"}': 40.0,
    'status="5xx"': 0.001,
    "payment_transactions_total": 121.3,
    "anomaly_score": 0.09,
    'sum(up{job="payment-service"})': 3,
    'count(up{job="payment-service"})': 3,
    'sum(up{job="auth-service"})': 1,
    "payment_db_pool_in_use": 3,
    "payment_db_pool_size": 10,
    "payment_db_errors_total": 0,
    "node_cpu_seconds_total": 31.2,
    "MemTotal": 16 * 1024**3,
    "MemAvailable": 6.2 * 1024**3,
    "filesystem_size": 100 * 1024**3,
    "filesystem_avail": 69 * 1024**3,
    "network_receive": 2_100_000,
}


@pytest.fixture
def viewer(auth):
    return bearer(auth.token("viewer@orbe.test"))


@pytest.fixture
def ops(auth):
    return bearer(auth.token("ops@orbe.test"))


def kpis(body):
    return {k["key"]: k for k in body["kpis"]}


# --- Mise en forme -----------------------------------------------------------------------------


def test_french_formatting():
    assert fmt.ms(2140.4) == "2 140 ms"
    assert fmt.percent(99.98, 2) == "99,98 %"
    assert fmt.score(0.094) == "0,09"
    assert fmt.duration(125) == "2 min 05 s"
    assert fmt.duration(40) == "40 s"
    assert fmt.percent(None) == fmt.MISSING


# --- Vue d'ensemble ----------------------------------------------------------------------------


def test_overview_nominal_without_remediation_engine(client, upstreams, viewer):
    upstreams.prom = dict(NOMINAL)

    response = client.get("/bo/supervision/overview", headers=viewer)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == {"label": "Opérationnel", "tone": "ok"}
    assert body["sources"] == {"prometheus": "up", "remediation": "down"}
    k = kpis(body)
    assert (k["availability"]["value"], k["availability"]["tone"]) == ("99,98 %", None)
    assert k["latency_p95"]["value"] == "182 ms"
    assert k["error_rate"]["value"] == "0,1 %"
    assert k["tx_per_min"]["value"] == "121"
    assert (k["anomaly_score"]["value"], k["anomaly_score"]["tone"]) == ("0,09", "ok")
    assert k["mttr"]["tone"] == "unknown"


def test_overview_during_an_incident(client, upstreams, viewer):
    upstreams.prom = {
        **NOMINAL,
        'highr_seconds_bucket{job="payment-service"}': 2140,
        'status="5xx"': 0.078,
        "anomaly_score": 0.94,
    }
    upstreams.status = {
        "platform": "remediation",
        "payments_enabled": False,
        "updated_at": "2026-10-21T08:42:11Z",
        "services": [{"name": "payment-service", "state": "degraded"}],
        "incident": {"id": "INC-0007", "detected_at": "2026-10-21T08:42:07Z", "recovered_at": None},
    }

    body = client.get("/bo/supervision/overview", headers=viewer).json()

    assert body["status"] == {"label": "Remédiation en cours", "tone": "danger"}
    assert body["banner"]["meta"] == "Ouvert à 10:42:07 · INC-0007"  # heure de Paris
    k = kpis(body)
    assert (k["latency_p95"]["tone"], k["latency_p95"]["sub"]) == ("danger", "Seuil 800 ms dépassé")
    assert k["error_rate"]["tone"] == "danger"
    assert k["anomaly_score"]["tone"] == "danger"
    assert (k["mttr"]["value"], k["mttr"]["sub"]) == ("en cours", "INC-0007")


def test_overview_after_recovery(client, upstreams, viewer):
    upstreams.prom = dict(NOMINAL)
    upstreams.status = {
        "platform": "recovered",
        "services": [{"name": "payment-service", "state": "recovered"}],
        "incident": {
            "id": "INC-0007",
            "detected_at": "2026-10-21T08:42:07Z",
            "recovered_at": "2026-10-21T08:44:12Z",
            "verified_by": "tx_9c01e7aa",
        },
    }

    body = client.get("/bo/supervision/overview", headers=viewer).json()

    assert body["status"] == {"label": "Rétabli", "tone": "ok"}
    assert body["banner"]["text"] == (
        "Service rétabli à 10:44:12. Vérifié par la transaction test tx_9c01e7aa."
    )
    assert body["banner"]["meta"] == "MTTR 2 min 05 s · INC-0007"
    assert kpis(body)["mttr"]["raw"] == 125


def test_overview_when_payment_is_down_and_no_engine(client, upstreams, viewer):
    upstreams.prom = {**NOMINAL, 'sum(up{job="payment-service"})': 0}

    body = client.get("/bo/supervision/overview", headers=viewer).json()

    assert body["status"]["tone"] == "danger"
    assert body["banner"]["text"] == "payment-service ne répond plus."


def test_overview_survives_prometheus_outage(client, upstreams, viewer):
    upstreams.down = {"prometheus", "remediation"}

    response = client.get("/bo/supervision/overview", headers=viewer)

    assert response.status_code == 200
    body = response.json()
    assert body["status"]["tone"] == "unknown"
    assert body["sources"] == {"prometheus": "down", "remediation": "down"}
    assert all(k["value"] == fmt.MISSING for k in body["kpis"])


# --- Services, courbes, ressources -------------------------------------------------------------


def test_services_cards(client, upstreams, viewer):
    upstreams.prom = {**NOMINAL, "payment_db_pool_in_use": 9}
    upstreams.status = {
        "platform": "recovered",
        "services": [
            {"name": "payment-service", "state": "recovered"},
            {"name": "waf", "state": "ok"},
        ],
        "incident": {"recovered_at": "2026-10-21T08:44:12Z"},
    }

    cards = {
        c["name"]: c
        for c in client.get("/bo/supervision/services", headers=viewer).json()["services"]
    }

    assert cards["payment-service"]["status"] == "restored"
    assert cards["payment-service"]["metric"] == "3/3 instance(s) · 182 ms"
    assert cards["auth-service"] == {
        "name": "auth-service",
        "desc": "Authentification · mot de passe + visage",
        "status": "ok",
        "metric": "40 ms",
    }
    assert (cards["mariadb"]["status"], cards["mariadb"]["metric"]) == (
        "warn",
        "pool 9/10 connexions",
    )
    assert cards["waf"]["status"] == "ok"
    assert cards["remediation-engine"]["metric"] == "dernier run OK"
    assert cards["detector-ml"]["metric"] == "score 0,09"


def test_services_are_unknown_without_measures(client, upstreams, viewer):
    upstreams.down = {"prometheus", "remediation"}

    cards = client.get("/bo/supervision/services", headers=viewer).json()["services"]

    assert {c["status"] for c in cards} == {"unknown"}


def test_series_one_point_per_minute_with_incident_window(client, upstreams, viewer):
    upstreams.prom = dict(NOMINAL)
    now = time.time()
    detected = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 300))
    upstreams.status = {"platform": "incident", "incident": {"detected_at": detected}}

    body = client.get("/bo/supervision/series", params={"minutes": 30}, headers=viewer).json()

    points = body["points"]
    assert len(points) == 30
    assert points[-1]["latency"] == 182 and points[-1]["anomaly"] == 0.09
    assert points[-1]["tx"] == 121
    assert [p["incident"] for p in points[-6:]] == [True] * 6
    assert points[0]["incident"] is False
    assert body["incident"]["x2"] == points[-1]["time"]


def test_series_are_empty_when_prometheus_is_down(client, upstreams, viewer):
    upstreams.down = {"prometheus"}

    body = client.get("/bo/supervision/series", headers=viewer).json()

    assert len(body["points"]) == 30
    assert all(p["latency"] is None for p in body["points"])
    assert body["incident"] is None


def test_resources(client, upstreams, viewer):
    upstreams.prom = dict(NOMINAL)

    resources = client.get("/bo/supervision/resources", headers=viewer).json()["resources"]

    assert resources == [
        {"label": "CPU", "value": "31 %", "percent": 31.2},
        {"label": "Mémoire", "value": "9,8 / 16 Go", "percent": 61.3},
        {"label": "Disque", "value": "31 / 100 Go", "percent": 31.0},
        {"label": "Réseau entrant", "value": "2,1 Mo/s", "percent": 16.8},
    ]


# --- Journaux ----------------------------------------------------------------------------------


def loki_line(ts_ns, **data):
    return (ts_ns, {"container": "orbe-dev-payment-service-1"}, json.dumps(data))


def test_logs_are_redacted_and_most_recent_first(client, upstreams, viewer):
    base = int(time.time() * 1e9)
    upstreams.loki_lines = [
        loki_line(
            base - 2_000_000_000,
            level="warning",
            service="auth-service",
            msg="login_failed",
            reason="invalid_credentials",
            client_ip="203.0.113.42",
            client_id="11111111-1111-1111-1111-111111111111",
        ),
        loki_line(
            base, level="error", service="payment-service", msg="db_unavailable", path="/pay"
        ),
        loki_line(
            base - 1_000_000_000, level="info", service="auth-service", msg="session_revoked"
        ),
        (base - 3_000_000_000, {"container": "x"}, "ligne non JSON"),
    ]

    body = client.get("/bo/supervision/logs", params={"level": "warn"}, headers=viewer).json()

    logs = body["logs"]
    assert [entry["msg"] for entry in logs] == [
        "db_unavailable",
        "session_revoked",
        "login_failed · reason=invalid_credentials",
    ]
    assert [entry["level"] for entry in logs] == ["ERROR", "ACTION", "WARN"]
    assert logs[0]["source"] == "payment-service"
    assert "203.0.113.42" not in json.dumps(body) and "1111" not in json.dumps(body)
    query = upstreams.queries[-1]
    assert query.startswith('{container=~"orbe-.+"} | json')
    assert 'level=~"warning|error|critical"' in query and 'msg!="request"' in query


def test_access_logs_are_summarised(client, upstreams):
    line = log_line(
        1_761_036_127_552_000_000,
        {},
        json.dumps(
            {
                "level": "info",
                "service": "payment-service",
                "msg": "request",
                "method": "POST",
                "path": "/pay",
                "status": 201,
                "duration_ms": 12.5,
                "client_ip": "1.2.3.4",
            }
        ),  # fmt: skip
        "Europe/Paris",
    )

    assert line.msg == "POST /pay → 201 · 12.5 ms"
    assert line.time.endswith(".552")


def test_logs_source_filter_is_validated(client, viewer):
    response = client.get("/bo/supervision/logs", params={"source": 'x"} |= "'}, headers=viewer)

    assert response.status_code == 422  # pas d'injection LogQL


def test_logs_when_loki_is_down(client, upstreams, viewer):
    upstreams.down = {"loki"}

    response = client.get("/bo/supervision/logs", headers=viewer)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "loki_unavailable"


def test_supervision_requires_a_session(client):
    assert client.get("/bo/supervision/overview").status_code == 401
