from pathlib import Path

from base_agent_system.ingestion.models import IngestionDocument
from base_agent_system.ingestion.pipeline import ingest_documents


def test_ingest_documents_chunks_fake_connector_output(tmp_path: Path) -> None:
    source_path = tmp_path / "source.txt"
    source_path.write_text("placeholder", encoding="utf-8")

    result = ingest_documents(
        [
            IngestionDocument(
                source_path=source_path,
                title="Synthetic Source",
                content=(
                    "This synthetic source proves the ingestion pipeline can operate "
                    "on connector output without depending on markdown file loading."
                ),
            )
        ],
        chunk_size=60,
        chunk_overlap=10,
    )

    assert result.file_count == 1
    assert result.chunk_count >= 2
    assert result.documents[0].title == "Synthetic Source"
