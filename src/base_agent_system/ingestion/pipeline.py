"""Minimal markdown chunking pipeline backed by LlamaIndex."""

from pathlib import Path

from llama_index.core.node_parser import SentenceSplitter

from base_agent_system.ingestion.markdown_loader import load_markdown_documents
from base_agent_system.ingestion.models import IngestionResult, MarkdownChunk, MarkdownDocument


def ingest_markdown_directory(
    directory: Path,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> IngestionResult:
    documents = load_markdown_documents(directory)
    chunks = _chunk_documents(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return IngestionResult(documents=documents, chunks=chunks)


def _chunk_documents(
    documents: list[MarkdownDocument],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[MarkdownChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks: list[MarkdownChunk] = []
    for document in documents:
        for chunk_index, node in enumerate(
            splitter.get_nodes_from_documents([document.llama_document])
        ):
            chunks.append(
                MarkdownChunk(
                    source_path=document.source_path,
                    title=document.title,
                    chunk_index=chunk_index,
                    text=node.text,
                    node=node,
                )
            )
    return chunks
