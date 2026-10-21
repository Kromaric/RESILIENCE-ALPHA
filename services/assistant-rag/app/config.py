from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration lue dans l'environnement (préfixe RAG_). Voir CADRAGE §4.8 et §10.

    L'assistant est en lecture seule : il lit le corpus docs/ (monté en lecture seule), interroge
    Ollama et ne dispose d'aucun accès au moteur de remédiation, au socket Docker ni à la base.
    """

    model_config = SettingsConfigDict(env_prefix="RAG_", extra="ignore", env_ignore_empty=True)

    service_name: str = "assistant-rag"
    log_level: str = "INFO"
    enable_docs: bool = False

    # Ollama sur la VM dédiée (infra/ollama/), derrière son proxy à jeton : http://<ip-vm>:11434
    ollama_base_url: str = "http://localhost:11434"
    # Jeton exigé par le proxy de la VM (en-tête Authorization: Bearer). Fichier absent : aucun
    # en-tête (Ollama local sans proxy, développement uniquement).
    ollama_token_file: Path = Path("/run/secrets/ollama_token")
    llm_model: str = "qwen2.5:3b"
    embed_model: str = "nomic-embed-text"
    # Préfixes de tâche de nomic-embed-text, appliqués seulement si le modèle est un « nomic »
    # (bge-m3 et la plupart des autres modèles n'en utilisent pas)
    embed_query_prefix: str = "search_query: "
    embed_document_prefix: str = "search_document: "
    temperature: float = 0.1
    # Modèles « à raisonnement » (qwen3…) : false désactive la phase de réflexion, inutile ici et
    # très lente sur CPU. Laisser vide pour un modèle sans raisonnement (qwen2.5, llama3.1).
    reasoning: bool | None = None
    num_ctx: int = 4096
    keep_alive: str = "30m"  # garde le modèle en mémoire : pas de chargement de 20 s en démo
    llm_timeout_seconds: float = 90.0
    # Une seule génération à la fois (CPU) ; au-delà, les questions attendent leur tour
    max_concurrent_answers: int = 1
    queue_timeout_seconds: float = 60.0

    # Corpus et index
    corpus_dir: Path = Path("/corpus")
    # Motifs exclus de l'indexation (relatifs au corpus)
    corpus_exclude: list[str] = ["api/*"]
    index_dir: Path = Path("/data/chroma")
    collection: str = "orbe-docs"
    chunk_size: int = 800
    chunk_overlap: int = 100

    # Récupération
    top_k: int = 4
    # Si le meilleur extrait a un score (similarité cosinus, 0–1) inférieur à ce seuil, la
    # question est jugée hors sujet : réponse « je ne sais pas » sans appeler le modèle.
    # Mesuré avec nomic-embed-text : questions du domaine 0,69–0,78, hors sujet 0,62–0,64.
    # À recalibrer avec eval/questions.yaml (métrique rag_retrieval_top_score), et à changer
    # avec le modèle d'embeddings (les échelles diffèrent).
    min_relevance: float = 0.66
    max_question_chars: int = 500

    # Clé exigée sur POST /ask (en-tête X-API-Key). Fichier absent → refus de démarrer, sauf
    # RAG_ALLOW_ANONYMOUS=true (tests locaux uniquement).
    api_key_file: Path = Path("/run/secrets/rag_api_key")
    allow_anonymous: bool = False

    def read_ollama_token(self) -> str | None:
        if self.ollama_token_file.exists():
            return self.ollama_token_file.read_text(encoding="utf-8").strip() or None
        return None

    def read_api_key(self) -> str | None:
        if self.api_key_file.exists():
            return self.api_key_file.read_text(encoding="utf-8").strip() or None
        return None
