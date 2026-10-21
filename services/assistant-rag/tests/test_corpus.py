from app.corpus import fingerprint, list_markdown, split_documents
from app.index import build_or_load
from tests.conftest import BagOfWordsEmbeddings


def test_api_folder_is_excluded(corpus):
    files = [p.relative_to(corpus).as_posix() for p in list_markdown(corpus, ["api/*"])]
    assert "api/README.md" not in files
    assert "alertes/catalogue-alertes.md" in files


def test_chunks_carry_source_and_section(corpus):
    files = list_markdown(corpus, ["api/*"])
    chunks = split_documents(files, corpus, chunk_size=800, chunk_overlap=100)
    payment = [c for c in chunks if c.metadata["section"].endswith("PaymentAnomaly")]
    assert len(payment) == 1
    assert payment[0].metadata["source"] == "alertes/catalogue-alertes.md"
    # Le titre est recopié en tête de l'extrait pour garder le contexte
    assert payment[0].page_content.startswith(
        "[alertes/catalogue-alertes.md] Catalogue des alertes > PaymentAnomaly"
    )


def test_fingerprint_changes_with_content(corpus):
    files = list_markdown(corpus, [])
    before = fingerprint(files, corpus, "model", 800)
    (corpus / "runbooks/sc01.md").write_text("# Modifié\n", encoding="utf-8")
    assert fingerprint(files, corpus, "model", 800) != before
    assert fingerprint(files, corpus, "autre-modele", 800) != fingerprint(
        files, corpus, "model", 800
    )


def test_index_is_reused_then_rebuilt(tmp_path, corpus):
    kwargs = dict(
        corpus_dir=corpus,
        exclude=["api/*"],
        index_dir=tmp_path / "index",
        collection="test-index",
        embeddings=BagOfWordsEmbeddings(),
        embed_model="bow",
        chunk_size=800,
        chunk_overlap=100,
    )
    build_or_load(**kwargs)
    manifest = (tmp_path / "index" / "manifest.json").read_text()
    build_or_load(**kwargs)  # inchangé : rechargement
    assert (tmp_path / "index" / "manifest.json").read_text() == manifest

    (corpus / "nouveau.md").write_text("# Nouveau\n\n## Section\n\nTexte.\n", encoding="utf-8")
    build_or_load(**kwargs)  # corpus modifié : reconstruction
    assert (tmp_path / "index" / "manifest.json").read_text() != manifest
