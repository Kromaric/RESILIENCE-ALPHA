"""assistant-rag — assistant opérateur en lecture seule (CADRAGE §4.8).

uvicorn app.main:create_app --factory --port 8005
"""

import asyncio
import contextlib
import hmac
import logging
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app.assistant import Assistant
from app.config import Settings
from app.index import PrefixedEmbeddings, build_or_load
from app.logging_setup import configure_logging, log_event, request_id_var
from app.metrics import ANSWER_SECONDS, INDEX_READY, QUESTIONS

logger = logging.getLogger("http")
QUIET_PATHS = {"/metrics", "/health/live", "/health/ready"}


class UTF8JSONResponse(JSONResponse):
    """Annonce l'encodage : sans « charset=utf-8 », Windows PowerShell 5.1 (Invoke-RestMethod)
    décode la réponse en Latin-1 et affiche « Ã© » au lieu de « é »."""

    media_type = "application/json; charset=utf-8"


class AskIn(BaseModel):
    question: str = Field(
        min_length=3, examples=["L'alerte PaymentAnomaly s'est déclenchée, que faire ?"]
    )


class SourceOut(BaseModel):
    doc: str
    section: str
    extrait: str
    score: float


class AskOut(BaseModel):
    answer: str
    sources: list[SourceOut]


def ollama_headers(settings: Settings) -> dict[str, str]:
    token = settings.read_ollama_token()
    return {"Authorization": f"Bearer {token}"} if token else {}


def default_embeddings(settings: Settings) -> Embeddings:
    from langchain_ollama import OllamaEmbeddings

    inner = OllamaEmbeddings(
        model=settings.embed_model,
        base_url=settings.ollama_base_url,
        client_kwargs={"headers": ollama_headers(settings), "timeout": 60},
    )
    if "nomic" not in settings.embed_model:
        return inner
    return PrefixedEmbeddings(inner, settings.embed_query_prefix, settings.embed_document_prefix)


def default_llm(settings: Settings) -> BaseChatModel:
    from langchain_ollama import ChatOllama

    extra = {} if settings.reasoning is None else {"reasoning": settings.reasoning}
    return ChatOllama(
        **extra,
        model=settings.llm_model,
        base_url=settings.ollama_base_url,
        temperature=settings.temperature,
        num_ctx=settings.num_ctx,
        keep_alive=settings.keep_alive,
        client_kwargs={
            "headers": ollama_headers(settings),
            "timeout": settings.llm_timeout_seconds,
        },
    )


def create_app(
    settings: Settings | None = None,
    embeddings_factory: Callable[[Settings], Embeddings] = default_embeddings,
    llm_factory: Callable[[Settings], BaseChatModel] = default_llm,
) -> FastAPI:
    """Fabrique de l'application. Embeddings et LLM sont injectables (tests sans Ollama)."""
    settings = settings or Settings()
    configure_logging(settings.service_name, settings.log_level)

    api_key = settings.read_api_key()
    if api_key is None and not settings.allow_anonymous:
        raise RuntimeError(
            f"Clé d'API absente ({settings.api_key_file}) : lancez scripts/init_dev_secrets.py "
            "ou, pour un test local uniquement, RAG_ALLOW_ANONYMOUS=true"
        )

    state: dict = {"assistant": None, "error": None}
    gate = asyncio.Semaphore(settings.max_concurrent_answers)

    async def prepare() -> None:
        """Construit l'index puis préchauffe le modèle. Réessaie tant qu'Ollama n'est pas prêt."""
        delay = 2.0
        while state["assistant"] is None:
            try:
                store = await asyncio.to_thread(
                    build_or_load,
                    corpus_dir=settings.corpus_dir,
                    exclude=settings.corpus_exclude,
                    index_dir=settings.index_dir,
                    collection=settings.collection,
                    embeddings=embeddings_factory(settings),
                    embed_model=settings.embed_model,
                    chunk_size=settings.chunk_size,
                    chunk_overlap=settings.chunk_overlap,
                )
                llm = llm_factory(settings)
                state["assistant"] = Assistant(
                    store, llm, top_k=settings.top_k, min_relevance=settings.min_relevance
                )
                state["error"] = None
                INDEX_READY.set(1)
            except Exception as exc:  # Ollama pas encore démarré, modèle absent…
                state["error"] = f"{type(exc).__name__}: {exc}"[:300]
                log_event(
                    logging.getLogger("app"),
                    "index_not_ready",
                    level=logging.WARNING,
                    error=state["error"],
                    retry_in_s=delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)
        # Préchauffage : charge le LLM en mémoire avant la première vraie question
        try:
            await state["assistant"].llm.ainvoke([HumanMessage("Réponds simplement : prêt.")])
            log_event(logging.getLogger("app"), "llm_warmed_up", model=settings.llm_model)
        except Exception as exc:
            log_event(
                logging.getLogger("app"),
                "llm_warmup_failed",
                level=logging.WARNING,
                error=f"{type(exc).__name__}: {exc}"[:300],
            )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log_event(
            logging.getLogger("app"),
            "service_started",
            llm=settings.llm_model,
            embed=settings.embed_model,
            ollama=settings.ollama_base_url,
        )
        task = asyncio.create_task(prepare())
        app.state.prepare_task = task
        yield
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    app = FastAPI(
        title="Orbe — assistant-rag",
        version="0.1.0",
        description=(
            "Assistant opérateur en lecture seule : répond à partir de la documentation `docs/` "
            "(RAG local, Ollama + LangChain + ChromaDB) et cite ses sources. Il ne déclenche "
            "aucune action et n'a accès ni au moteur de remédiation, ni à Docker, ni à la base.\n\n"
            "Authentification : en-tête `X-API-Key`. Voir CADRAGE §4.8."
        ),
        lifespan=lifespan,
        default_response_class=UTF8JSONResponse,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
    )
    app.state.settings = settings

    def check_key(x_api_key: str | None) -> None:
        if api_key is None:
            return
        if not x_api_key or not hmac.compare_digest(x_api_key.encode(), api_key.encode()):
            raise HTTPException(status_code=401, detail={"code": "invalid_api_key"})

    @app.post("/ask", response_model=AskOut, tags=["Assistant"])
    async def ask(body: AskIn, x_api_key: str | None = Header(default=None)) -> AskOut:
        """Pose une question sur la plateforme Orbe ; la réponse cite ses sources."""
        check_key(x_api_key)
        question = body.question.strip()
        if len(question) > settings.max_question_chars:
            raise HTTPException(status_code=422, detail={"code": "question_too_long"})
        assistant: Assistant | None = state["assistant"]
        if assistant is None:
            raise HTTPException(
                status_code=503,
                detail={"code": "index_not_ready", "message": "Indexation en cours, réessayez."},
                headers={"Retry-After": "5"},
            )

        start = time.perf_counter()
        try:
            await asyncio.wait_for(gate.acquire(), timeout=settings.queue_timeout_seconds)
        except TimeoutError:
            QUESTIONS.labels("busy").inc()
            raise HTTPException(
                status_code=503, detail={"code": "busy"}, headers={"Retry-After": "10"}
            ) from None
        try:
            result = await asyncio.wait_for(
                assistant.ask(question), timeout=settings.llm_timeout_seconds
            )
        except Exception as exc:
            QUESTIONS.labels("llm_error").inc()
            log_event(
                logging.getLogger("app"),
                "answer_failed",
                level=logging.ERROR,
                error=f"{type(exc).__name__}: {exc}"[:300],
            )
            raise HTTPException(status_code=503, detail={"code": "llm_unavailable"}) from None
        finally:
            gate.release()

        elapsed = time.perf_counter() - start
        ANSWER_SECONDS.observe(elapsed)
        QUESTIONS.labels(result.outcome).inc()
        # Pas le texte de la question dans les journaux : seulement sa taille et les sources
        log_event(
            logging.getLogger("app"),
            "question_answered",
            outcome=result.outcome,
            question_chars=len(question),
            sources=[s.doc for s in result.sources],
            duration_ms=round(elapsed * 1000),
        )
        return AskOut(
            answer=result.answer,
            sources=[SourceOut(**s.__dict__) for s in result.sources],
        )

    @app.get("/health/live", include_in_schema=False)
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", include_in_schema=False)
    async def ready() -> JSONResponse:
        if state["assistant"] is None:
            return JSONResponse(
                status_code=503,
                content={"status": "indexing", "error": state["error"]},
            )
        return JSONResponse({"status": "ok"})

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            if request.url.path not in QUIET_PATHS:
                log_event(
                    logger,
                    "request",
                    method=request.method,
                    path=request.url.path,
                    status=status_code,
                    duration_ms=round((time.perf_counter() - start) * 1000, 1),
                )
            request_id_var.reset(token)

    return app
