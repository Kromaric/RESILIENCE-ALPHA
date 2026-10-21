"""Métriques de l'assistant (exposées sur /metrics, scrapées par Prometheus)."""

from prometheus_client import Counter, Gauge, Histogram

QUESTIONS = Counter(
    "rag_questions_total",
    "Questions reçues",
    ["outcome"],  # answered | no_context | refused_action | refused_secret | busy | llm_error
)
ANSWER_SECONDS = Histogram(
    "rag_answer_seconds",
    "Durée de traitement d'une question (récupération + génération)",
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 90),
)
RETRIEVAL_TOP_SCORE = Histogram(
    "rag_retrieval_top_score",
    "Score de pertinence du meilleur extrait retrouvé",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)
INDEX_CHUNKS = Gauge("rag_index_chunks", "Extraits présents dans l'index")
INDEX_READY = Gauge("rag_index_ready", "1 quand l'index est prêt à répondre")
