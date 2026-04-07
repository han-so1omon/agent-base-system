from __future__ import annotations

from pathlib import Path

from base_agent_system.ingestion.markdown_loader import load_markdown_documents
from base_agent_system.ingestion.models import IngestionDocument


class MarkdownDirectoryConnector:
    def load(self, source: str | Path) -> list[IngestionDocument]:
        return load_markdown_documents(Path(source))
