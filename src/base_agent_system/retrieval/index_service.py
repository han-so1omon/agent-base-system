"""Minimal LlamaIndex-backed retrieval service built on ingested markdown chunks."""

from __future__ import annotations

from hashlib import sha256
from math import sqrt
from pathlib import Path
from typing import Any

from llama_index.core import StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.base.response.schema import NodeWithScore

from base_agent_system.ingestion.models import MarkdownChunk
from base_agent_system.retrieval.models import Citation, RetrievalResult


_EMBED_DIM = 64
_SYNONYMS = {
    "search": "retrieve",
    "find": "retrieve",
    "retrieval": "retrieve",
    "retrieving": "retrieve",
    "searched": "retrieve",
    "chunked": "chunk",
    "chunking": "chunk",
    "chunks": "chunk",
    "normalized": "normalize",
    "normalization": "normalize",
    "documents": "document",
    "docs": "document",
    "doc": "document",
    "ingestion": "ingest",
}


class LocalHashEmbedding(BaseEmbedding):
    embed_dim: int

    def __init__(self, embed_dim: int = _EMBED_DIM, **kwargs: Any) -> None:
        super().__init__(embed_dim=embed_dim, **kwargs)

    @classmethod
    def class_name(cls) -> str:
        return "LocalHashEmbedding"

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._embed(query)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._embed(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._embed(text)

    async def _aget_text_embedding(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.embed_dim
        for term in _expanded_terms(text):
            digest = sha256(term.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.embed_dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class RetrievalIndex:
    def __init__(self, index: VectorStoreIndex, *, chunk_count: int) -> None:
        self._index = index
        self._chunk_count = chunk_count

    @property
    def chunk_count(self) -> int:
        return self._chunk_count

    def query(self, text: str, *, top_k: int) -> list[RetrievalResult]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")

        query_terms = set(_expanded_terms(text))
        if not query_terms:
            return []

        retriever = self._index.as_retriever(similarity_top_k=top_k)
        raw_results = retriever.retrieve(text)
        return [
            _to_retrieval_result(result, query=text, query_terms=query_terms)
            for result in raw_results
            if _matches_query(result, query_terms)
        ]


def build_or_load_index(
    *,
    index_dir: Path,
    chunks: list[MarkdownChunk] | None = None,
) -> RetrievalIndex:
    if chunks is not None:
        return _build_index(index_dir=index_dir, chunks=chunks)
    if not index_dir.exists():
        raise ValueError("chunks are required when building a new index")
    return _load_index(index_dir)


def _build_index(*, index_dir: Path, chunks: list[MarkdownChunk]) -> RetrievalIndex:
    index_dir.mkdir(parents=True, exist_ok=True)
    index = VectorStoreIndex(
        [chunk.node for chunk in chunks],
        embed_model=LocalHashEmbedding(embed_dim=_EMBED_DIM),
    )
    index.storage_context.persist(persist_dir=str(index_dir))
    return RetrievalIndex(index, chunk_count=len(chunks))


def _load_index(index_dir: Path) -> RetrievalIndex:
    storage_context = StorageContext.from_defaults(persist_dir=str(index_dir))
    index = load_index_from_storage(
        storage_context,
        embed_model=LocalHashEmbedding(embed_dim=_EMBED_DIM),
    )
    docstore_docs = storage_context.docstore.docs.values()
    chunk_count = sum(1 for doc in docstore_docs if getattr(doc, "text", None))
    return RetrievalIndex(index, chunk_count=chunk_count)


def _matches_query(result: NodeWithScore, query_terms: set[str]) -> bool:
    node_terms = set(_expanded_terms(result.node.text))
    return bool(query_terms.intersection(node_terms))


def _to_retrieval_result(
    result: NodeWithScore,
    *,
    query: str,
    query_terms: set[str],
) -> RetrievalResult:
    metadata = result.node.metadata
    text = result.node.text
    return RetrievalResult(
        text=text,
        score=float(result.score or 0.0),
        citation=Citation(
            path=str(metadata.get("path", "")),
            snippet=_snippet_for_query(text, query=query, query_terms=query_terms),
        ),
    )


def _snippet_for_query(
    text: str,
    *,
    query: str,
    query_terms: set[str],
    window: int = 80,
) -> str:
    lowered = text.lower()
    lowered_query = query.lower().strip()
    if lowered_query:
        start = lowered.find(lowered_query)
        if start >= 0:
            snippet_start = max(0, start - window // 2)
            snippet_end = min(len(text), start + len(lowered_query) + window // 2)
            return text[snippet_start:snippet_end].strip()
    for term in sorted(query_terms, key=len, reverse=True):
        start = lowered.find(term)
        if start >= 0:
            snippet_start = max(0, start - window // 2)
            snippet_end = min(len(text), start + len(term) + window // 2)
            return text[snippet_start:snippet_end].strip()
    return text[:window].strip()


def _tokenize(text: str) -> list[str]:
    import re

    return re.findall(r"[a-z0-9]+", text.lower())


def _expanded_terms(text: str) -> list[str]:
    expanded: list[str] = []
    for term in _tokenize(text):
        canonical = _canonicalize(term)
        expanded.append(canonical)
        synonym = _SYNONYMS.get(canonical)
        if synonym and synonym != canonical:
            expanded.append(synonym)
    return expanded


def _canonicalize(term: str) -> str:
    if term in _SYNONYMS:
        return _SYNONYMS[term]
    if len(term) > 4 and term.endswith("ing"):
        return term[:-3]
    if len(term) > 3 and term.endswith("ed"):
        return term[:-2]
    if len(term) > 3 and term.endswith("s"):
        return term[:-1]
    return term
