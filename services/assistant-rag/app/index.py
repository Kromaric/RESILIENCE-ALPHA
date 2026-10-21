"""Index vectoriel ChromaDB persistant, reconstruit seulement si le corpus a changé."""

import json
import logging
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.corpus import fingerprint, list_markdown, split_documents
from app.logging_setup import log_event
from app.metrics import INDEX_CHUNKS

logger = logging.getLogger("index")
MANIFEST = "manifest.json"


class PrefixedEmbeddings(Embeddings):
    """Préfixes de tâche de nomic-embed-text : « search_query: » et « search_document: »."""

    def __init__(self, inner: Embeddings, query_prefix: str = "", document_prefix: str = ""):
        self.inner = inner
        self.query_prefix = query_prefix
        self.document_prefix = document_prefix

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.inner.embed_documents([self.document_prefix + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self.inner.embed_query(self.query_prefix + text)


def build_or_load(
    *,
    corpus_dir: Path,
    exclude: list[str],
    index_dir: Path,
    collection: str,
    embeddings: Embeddings,
    embed_model: str,
    chunk_size: int,
    chunk_overlap: int,
) -> Chroma:
    files = list_markdown(corpus_dir, exclude)
    if not files:
        raise RuntimeError(f"Aucun fichier Markdown dans {corpus_dir}")
    expected = fingerprint(files, corpus_dir, embed_model, chunk_size, chunk_overlap, exclude)

    index_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = index_dir / MANIFEST
    store = _open(index_dir, collection, embeddings)
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("fingerprint") == expected:
            INDEX_CHUNKS.set(manifest.get("chunks", 0))
            log_event(logger, "index_loaded", chunks=manifest.get("chunks"), files=len(files))
            return store

    # Corpus modifié (ou premier démarrage) : reconstruction complète, simple et déterministe.
    # La collection est supprimée par l'API Chroma (pas en effaçant ses fichiers, qu'un client
    # ouvert peut encore tenir).
    manifest_path.unlink(missing_ok=True)
    store.delete_collection()
    store = _open(index_dir, collection, embeddings)

    chunks: list[Document] = split_documents(files, corpus_dir, chunk_size, chunk_overlap)
    ids = [f"{d.metadata['source']}#{d.metadata['section']}#{d.metadata['part']}" for d in chunks]
    # Identifiants uniques même si deux sections portent le même titre
    ids = [f"{i}-{n}" for n, i in enumerate(ids)]
    for start in range(0, len(chunks), 64):
        store.add_documents(chunks[start : start + 64], ids=ids[start : start + 64])

    manifest_path.write_text(
        json.dumps({"fingerprint": expected, "chunks": len(chunks), "files": len(files)}),
        encoding="utf-8",
    )
    INDEX_CHUNKS.set(len(chunks))
    log_event(logger, "index_built", chunks=len(chunks), files=len(files))
    return store


def _open(index_dir: Path, collection: str, embeddings: Embeddings) -> Chroma:
    return Chroma(
        collection_name=collection,
        embedding_function=embeddings,
        persist_directory=str(index_dir),
        collection_metadata={"hnsw:space": "cosine"},  # score de pertinence = 1 − distance cosinus
    )
