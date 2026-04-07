from pathlib import Path

from base_agent_system.ingestion.pipeline import ingest_markdown_directory


def test_ingest_markdown_directory_loads_chunks_with_metadata(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    markdown_file = docs_dir / "example.md"
    markdown_file.write_text(
        "# Example Seed Document\n\n"
        "This seed document explains the markdown ingestion service.\n\n"
        "It should be discovered, normalized, and chunked for retrieval.\n",
        encoding="utf-8",
    )

    result = ingest_markdown_directory(docs_dir, chunk_size=70, chunk_overlap=10)

    assert result.file_count == 1
    assert len(result.documents) == 1
    assert result.documents[0].source_path == markdown_file
    assert result.documents[0].title == "Example Seed Document"
    assert "markdown ingestion service" in result.documents[0].content
    assert result.documents[0].llama_document.metadata == {
        "path": str(markdown_file),
        "title": "Example Seed Document",
    }

    assert result.chunk_count >= 2
    assert len(result.chunks) == result.chunk_count

    first_chunk = result.chunks[0]
    assert first_chunk.source_path == markdown_file
    assert first_chunk.title == "Example Seed Document"
    assert first_chunk.chunk_index == 0
    assert first_chunk.text
    assert first_chunk.node.metadata == {
        "path": str(markdown_file),
        "title": "Example Seed Document",
    }
    assert first_chunk.node.text == first_chunk.text

    assert any(
        "discovered, normalized, and chunked" in chunk.text
        for chunk in result.chunks
    )
