from pathlib import Path

from base_agent_system.ingestion.pipeline import ingest_markdown_directory
from base_agent_system.retrieval.index_service import build_or_load_index


def test_build_or_load_index_returns_relevant_chunks_with_citations(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    markdown_file = docs_dir / "example.md"
    markdown_file.write_text(
        "# Example Seed Document\n\n"
        "This seed document explains the markdown ingestion service.\n\n"
        "It should be discovered, normalized, and chunked for retrieval.\n",
        encoding="utf-8",
    )

    ingestion_result = ingest_markdown_directory(docs_dir, chunk_size=70, chunk_overlap=10)
    index_dir = tmp_path / "retrieval-index"

    built_index = build_or_load_index(index_dir=index_dir, chunks=ingestion_result.chunks)
    loaded_index = build_or_load_index(index_dir=index_dir)

    results = loaded_index.query("What should be chunked for retrieval?", top_k=2)

    assert index_dir.exists()
    assert built_index.chunk_count == ingestion_result.chunk_count
    assert loaded_index.chunk_count == ingestion_result.chunk_count
    assert len(results) >= 1

    best_result = results[0]
    assert best_result.citation.path == str(markdown_file)
    assert "chunked" in best_result.citation.snippet
    assert "normalized" in best_result.text
    assert best_result.score > 0


def test_query_excludes_unrelated_zero_score_results(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "example.md").write_text(
        "# Example Seed Document\n\n"
        "This seed document explains the markdown ingestion service.\n",
        encoding="utf-8",
    )

    ingestion_result = ingest_markdown_directory(docs_dir, chunk_size=70, chunk_overlap=10)
    index = build_or_load_index(
        index_dir=tmp_path / "retrieval-index",
        chunks=ingestion_result.chunks,
    )

    results = index.query("orbital mechanics and telescope arrays", top_k=3)

    assert results == []


def test_build_or_load_index_uses_fresh_chunks_instead_of_stale_disk_state(
    tmp_path: Path,
) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    markdown_file = docs_dir / "example.md"
    markdown_file.write_text(
        "# Example Seed Document\n\n"
        "Stale persisted chunk about unrelated warehouse inventory.\n",
        encoding="utf-8",
    )

    stale_ingestion = ingest_markdown_directory(docs_dir, chunk_size=80, chunk_overlap=10)
    stale_index_dir = tmp_path / "retrieval-index"

    build_or_load_index(
        index_dir=stale_index_dir,
        chunks=stale_ingestion.chunks,
    )

    markdown_file.write_text(
        "# Example Seed Document\n\n"
        "Fresh retrieval text should be preferred over stale disk state.\n",
        encoding="utf-8",
    )
    fresh_ingestion = ingest_markdown_directory(docs_dir, chunk_size=80, chunk_overlap=10)

    fresh_index = build_or_load_index(
        index_dir=stale_index_dir,
        chunks=fresh_ingestion.chunks,
    )

    results = fresh_index.query("fresh retrieval text", top_k=1)

    assert fresh_index.chunk_count == fresh_ingestion.chunk_count
    assert len(results) == 1
    assert "Fresh retrieval text" in results[0].text


def test_query_supports_short_semantic_terms(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    markdown_file = docs_dir / "example.md"
    markdown_file.write_text(
        "# AI Notes\n\n"
        "AI agents rely on retrieval to ground responses in available context.\n",
        encoding="utf-8",
    )

    ingestion_result = ingest_markdown_directory(docs_dir, chunk_size=80, chunk_overlap=10)
    index = build_or_load_index(
        index_dir=tmp_path / "retrieval-index",
        chunks=ingestion_result.chunks,
    )

    results = index.query("AI retrieval", top_k=1)

    assert len(results) == 1
    assert results[0].citation.path == str(markdown_file)
