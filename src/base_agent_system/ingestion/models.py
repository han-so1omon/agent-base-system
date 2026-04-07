"""Data models for document ingestion."""

from dataclasses import dataclass
from pathlib import Path

from llama_index.core.schema import Document, TextNode


@dataclass(frozen=True)
class IngestionDocument:
    source_path: Path
    title: str
    content: str

    @property
    def llama_document(self) -> Document:
        return Document(
            text=self.content,
            metadata={"path": str(self.source_path), "title": self.title},
        )


MarkdownDocument = IngestionDocument


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
