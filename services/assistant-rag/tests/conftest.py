"""Tests sans Ollama : embeddings « sac de mots » déterministes et LLM factice."""

import hashlib
import math
import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.config import Settings
from app.main import create_app

DIM = 256
API_KEY = "test-key"


class BagOfWordsEmbeddings(Embeddings):
    """Vecteur de fréquences de mots hachés : deux textes qui partagent des mots sont proches."""

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * DIM
        for word in re.findall(r"[a-zà-ÿ0-9_]{3,}", text.lower()):
            vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0  # noqa: S324
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


CORPUS = {
    "alertes/catalogue-alertes.md": """# Catalogue des alertes

## PaymentAnomaly

Le score anomaly_score de payment-service dépasse le seuil pendant 10 s. Le moteur de
remédiation est déclenché automatiquement et exécute pb-contain-and-recover.yml.

## ServiceDown

Prometheus n'arrive plus à collecter les métriques du service.
""",
    "runbooks/sc01.md": """# Runbook SC-01

## SC-01 — actions automatiques

Le moteur bloque les IP au WAF, redémarre les instances payment-service dégradées puis vérifie
la reprise avec trois transactions de la sonde.
""",
    "api/README.md": "# API\n\nFichier exclu de l'indexation : paymentanomaly paymentanomaly.\n",
}


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    for rel, text in CORPUS.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def settings(tmp_path: Path, corpus: Path) -> Settings:
    key = tmp_path / "rag_api_key"
    key.write_text(API_KEY)
    return Settings(
        corpus_dir=corpus,
        index_dir=tmp_path / "index",
        collection=f"test-{tmp_path.name}",
        api_key_file=key,
        embed_query_prefix="",
        embed_document_prefix="",
        min_relevance=0.2,
    )


def wait_ready(client: TestClient, timeout: float = 15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if client.get("/health/ready").status_code == 200:
            return
        time.sleep(0.05)
    raise AssertionError(client.get("/health/ready").json())


@pytest.fixture
def client(settings: Settings):
    llm = FakeListChatModel(responses=["prêt"] + ["Réponse de test [1]"] * 20)
    app = create_app(
        settings,
        embeddings_factory=lambda s: BagOfWordsEmbeddings(),
        llm_factory=lambda s: llm,
    )
    with TestClient(app) as c:
        wait_ready(c)
        yield c
