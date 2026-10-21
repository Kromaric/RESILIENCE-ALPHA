import json
from urllib.parse import parse_qs, urlparse

from conftest import bearer


def test_incidents_are_relayed_as_is(client, upstreams, auth):
    upstreams.incidents = {"items": [{"id": "INC-0007", "steps": [{"title": "Détection"}]}]}
    headers = bearer(auth.token("viewer@orbe.test"))

    listing = client.get("/bo/incidents", headers=headers)
    detail = client.get("/bo/incidents/INC-0007", headers=headers)
    missing = client.get("/bo/incidents/INC-9999", headers=headers)

    assert listing.json() == upstreams.incidents
    assert detail.json()["steps"] == [{"title": "Détection"}]
    assert missing.status_code == 404


def test_incident_id_is_validated(client, auth):
    response = client.get("/bo/incidents/..%2Fstatus", headers=bearer(auth.token()))

    assert response.status_code in (404, 422)


def test_incidents_when_engine_is_down(client, upstreams, auth):
    upstreams.down = {"remediation"}

    response = client.get("/bo/incidents", headers=bearer(auth.token()))

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "remediation_unavailable"


def test_assistant_question_is_relayed(client, upstreams, auth, caplog):
    upstreams.answer = {
        "answer": "Le moteur applique la règle R-03.",
        "sources": [{"doc": "runbook-payment.md", "extrait": "Le moteur choisit la règle…"}],
    }

    response = client.post(
        "/bo/assistant/ask",
        json={"question": "Que fait le moteur ? mon mot de passe est secret123"},
        headers=bearer(auth.token("ops@orbe.test")),
    )

    assert response.status_code == 200, response.text
    assert response.json()["sources"][0]["doc"] == "runbook-payment.md"
    assert json.loads(upstreams.queries[-1])["question"].startswith("Que fait")
    assert all("secret123" not in record.getMessage() for record in caplog.records)
    assert all("secret123" not in str(getattr(r, "fields", "")) for r in caplog.records)


def test_assistant_is_reserved_to_operators(client, auth):
    response = client.post(
        "/bo/assistant/ask",
        json={"question": "Bonjour ?"},
        headers=bearer(auth.token("viewer@orbe.test")),
    )

    assert response.status_code == 403


def test_assistant_is_rate_limited_per_operator(client, upstreams, auth):
    upstreams.answer = {"answer": "ok", "sources": []}
    headers = bearer(auth.token("ops@orbe.test"))

    codes = [
        client.post(
            "/bo/assistant/ask", json={"question": "Question ?"}, headers=headers
        ).status_code
        for _ in range(4)
    ]

    assert codes == [200, 200, 200, 429]


def test_assistant_down(client, upstreams, auth):
    upstreams.down = {"assistant"}

    response = client.post(
        "/bo/assistant/ask", json={"question": "Question ?"}, headers=bearer(auth.token())
    )

    assert response.status_code == 503


def test_grafana_links(client, auth):
    body = client.get("/bo/grafana", headers=bearer(auth.token("viewer@orbe.test"))).json()

    assert body["base_url"] == "http://grafana.test:3000"
    assert (
        body["dashboards"][0]["url"]
        == "http://grafana.test:3000/d/orbe-supervision/orbe-supervision"
    )
    latency = next(p for p in body["panels"] if p["key"] == "latency")
    url = urlparse(latency["embed_url"])
    assert url.path == "/d-solo/orbe-supervision/orbe-supervision"
    assert parse_qs(url.query)["panelId"] == ["1"]
    assert [t["title"] for t in body["tools"]] == ["Grafana", "Prometheus", "Loki — journaux"]


def test_grafana_panel_ids_match_the_provisioned_dashboard(client, auth):
    from pathlib import Path

    dashboard = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "infra/grafana-provisioning/dashboards/orbe-supervision.json"
        ).read_text(encoding="utf-8")
    )
    panels = {p["id"]: p["title"] for p in dashboard["panels"]}
    body = client.get("/bo/grafana", headers=bearer(auth.token())).json()

    for panel in body["panels"]:
        panel_id = int(parse_qs(urlparse(panel["embed_url"]).query)["panelId"][0])
        assert panels[panel_id] == panel["title"]
    assert dashboard["uid"] == "orbe-supervision"
