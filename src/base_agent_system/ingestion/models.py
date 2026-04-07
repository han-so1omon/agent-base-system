"""Data models for markdown ingestion."""

from dataclasses import dataclass
from pathlib import Path

from llama_index.core.schema import Document, TextNode


@dataclass(frozen=True)
class MarkdownDocument:
    source_path: Path
    title: str
    content: str
    llama_document: Document


@dataclass(frozen=True)
class MarkdownChunk:
    source_path: Path
    title: str
    chunk_index: int
    text: str
    node: TextNode


@dataclass(frozen=True)
class IngestionResult:
    documents: list[MarkdownDocument]
    chunks: list[MarkdownChunk]

    @property
    def file_count(self) -> int:
        return len(self.documents)

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)
