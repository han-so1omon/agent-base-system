"""Minimal shared runtime services for ingest and query flows."""

from __future__ import annotations

from pathlib import Path
import re
from tempfile import TemporaryDirectory
from typing import Any

from base_agent_system.config import Settings
from base_agent_system.checkpointing import build_postgres_checkpointer
from base_agent_system.memory.graphiti_service import GraphitiMemoryBackend
from base_agent_system.ingestion.pipeline import ingest_markdown_directory
from base_agent_system.memory.graphiti_service import GraphitiMemoryService
from base_agent_system.memory.models import MemoryEpisode
from base_agent_system.retrieval.index_service import RetrievalIndex, build_or_load_index
from base_agent_system.retrieval.models import RetrievalResult
from base_agent_system.workflow.graph import build_workflow


def build_runtime_services(
    settings: Settings,
    *,
    memory_backend: GraphitiMemoryBackend | None = None,
) -> tuple[object, object]:
    temp_dir = TemporaryDirectory(prefix="base-agent-system-index-")
    retrieval_service = _MutableRetrievalService()
    memory_service = GraphitiMemoryService(
        settings=settings,
        backend=memory_backend,
    )
    memory_service.initialize_indices()
    ingest_service = IngestService(
        settings=settings,
        retrieval_service=retrieval_service,
        index_dir=Path(temp_dir.name),
    )
    ingest_service.run(path=str(settings.docs_seed_path))
    workflow_service = WorkflowService(
        settings=settings,
        retrieval_service=retrieval_service,
        memory_service=memory_service,
        temp_dir=temp_dir,
    )
    return ingest_service, workflow_service


class IngestService:
    def __init__(
        self,
        *,
        settings: Settings,
        retrieval_service: "_MutableRetrievalService",
        index_dir: Path,
    ) -> None:
        self._settings = settings
        self._retrieval_service = retrieval_service
        self._index_dir = index_dir

    def run(self, *, path: str | None = None) -> dict[str, int]:
        directory = Path(path or self._settings.docs_seed_path)
        result = ingest_markdown_directory(
            directory,
            chunk_size=self._settings.chunk_size,
            chunk_overlap=self._settings.chunk_overlap,
        )
        index = build_or_load_index(index_dir=self._index_dir, chunks=result.chunks)
        self._retrieval_service.set_index(index)
        return {"file_count": result.file_count, "chunk_count": result.chunk_count}


class WorkflowService:
    def __init__(
        self,
        *,
        settings: Settings,
        retrieval_service: "_MutableRetrievalService",
        memory_service: GraphitiMemoryService,
        temp_dir: TemporaryDirectory[str],
    ) -> None:
        self._memory_service = memory_service
        self._temp_dir = temp_dir
        self._checkpointer = None
        self._checkpointer_holder = None
        if settings.postgres_uri:
            self._checkpointer_holder = build_postgres_checkpointer(settings.postgres_uri)
        if self._checkpointer_holder is not None:
            self._checkpointer = self._checkpointer_holder.open()
        self._app = build_workflow(
            settings=settings,
            retrieval_service=retrieval_service,
            memory_service=memory_service,
            checkpointer=self._checkpointer,
        )

    def run(self, *, thread_id: str, query: str) -> dict[str, Any]:
        invoke_kwargs: dict[str, Any] = {}
        if self._checkpointer is not None:
            invoke_kwargs["config"] = {"configurable": {"thread_id": thread_id}}

        result = self._app.invoke(
            {"thread_id": thread_id, "query": query},
            **invoke_kwargs,
        )
        return {
            "thread_id": result["thread_id"],
            "answer": result["answer"],
            "citations": result["citations"],
            "debug": result["debug"],
        }

    def close(self) -> None:
        self._memory_service.close()
        if self._checkpointer_holder is not None:
            self._checkpointer_holder.close()
            self._checkpointer = None
        self._temp_dir.cleanup()


class _MutableRetrievalService:
    def __init__(self) -> None:
        self._index: RetrievalIndex | None = None

    def set_index(self, index: RetrievalIndex) -> None:
        self._index = index

    def query(self, text: str, *, top_k: int) -> list[RetrievalResult]:
        if self._index is None:
            return []
        return self._index.query(text, top_k=top_k)


class _InMemoryGraphitiBackend:
    def __init__(self) -> None:
        self._initialized = False
        self._episodes: list[MemoryEpisode] = []

    def initialize_indices(self) -> None:
        self._initialized = True

    def store_episode(self, episode: MemoryEpisode) -> None:
        self._require_initialized()
        self._episodes.append(episode)

    def search_memory(
        self,
        query: str,
        *,
        thread_id: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        self._require_initialized()
        query_terms = set(_tokenize(query))
        matches: list[dict[str, Any]] = []
        for episode in self._episodes:
            if episode.thread_id != thread_id:
                continue
            episode_terms = set(_tokenize(episode.content))
            overlap = query_terms.intersection(episode_terms)
            score = float(len(overlap))
            if score <= 0:
                continue
            matches.append(
                {
                    "thread_id": episode.thread_id,
                    "actor": episode.actor,
                    "content": episode.content,
                    "score": score,
                }
            )
        matches.sort(key=lambda item: item["score"], reverse=True)
        return matches[:limit]

    def close(self) -> None:
        self._episodes.clear()
        self._initialized = False

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("memory backend must be initialized before use")

def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in _STOPWORDS and len(token) > 2
    }


_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "what",
    "does",
    "did",
    "you",
    "your",
    "earlier",
    "mention",
    "mentioned",
    "have",
    "from",
}
