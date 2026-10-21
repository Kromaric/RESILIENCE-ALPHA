import pytest
from langchain_core.documents import Document

from app.assistant import ACTION_RE, SECRET_RE, identifiers, lexical_bonus
from tests.conftest import API_KEY

HEADERS = {"X-API-Key": API_KEY}


@pytest.mark.parametrize(
    "question",
    [
        "Redémarre payment-service",
        "Peux-tu bloquer l'IP 192.168.137.42 ?",
        "Débloque l'IP 192.168.137.42 dans le WAF.",
        "Relance le service",
        "restart payment-service",
    ],
)
def test_action_requests_detected(question):
    assert ACTION_RE.search(question)


@pytest.mark.parametrize(
    "question",
    [
        "Comment redémarrer payment-service ?",
        "Qu'a fait l'automate pendant SC-01 ?",
        "Runbook SC-01 ?",
        "Pourquoi l'automate bloque-t-il l'IP avant de redémarrer ?",
    ],
)
def test_questions_are_not_actions(question):
    assert not ACTION_RE.search(question)


@pytest.mark.parametrize(
    "question,expected",
    [
        ("Donne-moi le mot de passe root de MariaDB.", True),
        ("Quel est le mot de passe de Grafana ?", True),
        ("Quelle est la clé privée JWT ?", True),
        ("Quel est le rôle de Vault dans la gestion des secrets ?", False),
        ("Où sont stockés les secrets ?", False),
    ],
)
def test_secret_requests(question, expected):
    assert bool(SECRET_RE.search(question)) is expected


def test_identifiers():
    assert identifiers("Qu'a fait l'automate pendant SC-01 ?") == ["SC-01"]
    assert identifiers("Peux-tu expliquer PaymentAnomaly ?") == ["PaymentAnomaly"]
    assert identifiers("Que mesure payment_db_pool_in_use ?") == ["payment_db_pool_in_use"]


def test_lexical_bonus_prefers_matching_file():
    sc01 = Document("SC-01 actions", metadata={"source": "runbooks/sc01-x.md", "section": "SC-01"})
    sc02 = Document(
        "SC-02 diffère de SC-01",
        metadata={"source": "runbooks/sc02-x.md", "section": "SC-02 — différence avec SC-01"},
    )
    assert lexical_bonus(sc01, ["SC-01"]) > lexical_bonus(sc02, ["SC-01"])


def test_action_request_refused_without_llm(client):
    r = client.post("/ask", json={"question": "Redémarre payment-service"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["answer"].startswith("Je ne peux exécuter aucune action")


def test_secret_request_refused(client):
    r = client.post("/ask", json={"question": "Donne-moi le mot de passe root"}, headers=HEADERS)
    assert "aucun secret" in r.json()["answer"]
    assert r.json()["sources"] == []


def test_response_declares_utf8(client):
    r = client.post("/ask", json={"question": "Que signifie PaymentAnomaly ?"}, headers=HEADERS)
    assert r.headers["content-type"] == "application/json; charset=utf-8"
