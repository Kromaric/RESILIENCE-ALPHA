"""Chargement et découpage du corpus Markdown (docs/).

Découpage en deux temps : par titres (une section = un sujet), puis en morceaux de
chunk_size caractères. Le chemin des titres est recopié en tête de chaque morceau, pour qu'un
extrait isolé garde son contexte (« PaymentAnomaly > Action automatique »).
"""

import hashlib
from fnmatch import fnmatch
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]


def list_markdown(corpus_dir: Path, exclude: list[str]) -> list[Path]:
    """Fichiers .md du corpus, hors motifs exclus (fnmatch : « api/* » couvre tout api/)."""
    files = []
    for path in sorted(corpus_dir.rglob("*.md")):
        rel = path.relative_to(corpus_dir).as_posix()
        if any(fnmatch(rel, pattern) for pattern in exclude):
            continue
        files.append(path)
    return files


def fingerprint(files: list[Path], corpus_dir: Path, *params: object) -> str:
    """Empreinte du corpus et des paramètres d'indexation (index reconstruit si elle change)."""
    digest = hashlib.sha256()
    for param in params:
        digest.update(repr(param).encode())
    for path in files:
        digest.update(path.relative_to(corpus_dir).as_posix().encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def split_documents(
    files: list[Path], corpus_dir: Path, chunk_size: int, chunk_overlap: int
) -> list[Document]:
    by_headers = MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS, strip_headers=True)
    by_size = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n| ", "\n", ". ", " ", ""],
    )
    chunks: list[Document] = []
    for path in files:
        source = path.relative_to(corpus_dir).as_posix()
        text = path.read_text(encoding="utf-8")
        for section in by_headers.split_text(text):
            trail = [section.metadata[key] for _, key in HEADERS if key in section.metadata]
            title = " > ".join(trail)
            for i, piece in enumerate(by_size.split_text(section.page_content)):
                if not piece.strip():
                    continue
                content = f"[{source}] {title}\n{piece}" if title else f"[{source}]\n{piece}"
                chunks.append(
                    Document(
                        page_content=content,
                        metadata={"source": source, "section": title, "part": i},
                    )
                )
    return chunks
