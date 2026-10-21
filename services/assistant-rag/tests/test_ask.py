import pytest

from app.config import Settings
from app.main import create_app
from tests.conftest import API_KEY

HEADERS = {"X-API-Key": API_KEY}


def test_answer_cites_relevant_source(client):
    r = client.post(
        "/ask",
        json={"question": "Que signifie l'alerte PaymentAnomaly sur payment-service ?"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "Réponse de test [1]"
    docs = [s["doc"] for s in body["sources"]]
    assert docs[0] == "alertes/catalogue-alertes.md"
    assert "api/README.md" not in docs
    assert all(0 <= s["score"] <= 1 for s in body["sources"])


def test_unrelated_question_says_it_does_not_know(client):
    r = client.post(
        "/ask", json={"question": "Recette de la tarte tatin aux pommes ?"}, headers=HEADERS
    )
    assert r.status_code == 200
    assert r.json()["sources"] == []
    assert "ne trouve pas" in r.json()["answer"]


def test_api_key_required(client):
    assert client.post("/ask", json={"question": "PaymentAnomaly ?"}).status_code == 401
    assert (
        client.post(
            "/ask", json={"question": "PaymentAnomaly ?"}, headers={"X-API-Key": "mauvaise"}
        ).status_code
        == 401
    )


def test_question_too_long(client):
    r = client.post("/ask", json={"question": "a" * 600}, headers=HEADERS)
    assert r.status_code == 422


def test_metrics_exposed(client):
    client.post("/ask", json={"question": "PaymentAnomaly ?"}, headers=HEADERS)
    text = client.get("/metrics").text
    assert "rag_questions_total" in text
    assert "rag_index_chunks" in text


def test_refuses_to_start_without_api_key(tmp_path, corpus):
    settings = Settings(corpus_dir=corpus, api_key_file=tmp_path / "absent")
    with pytest.raises(RuntimeError):
        create_app(settings)
