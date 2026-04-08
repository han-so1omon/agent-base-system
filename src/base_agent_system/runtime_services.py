"""Minimal shared runtime services for ingest and query flows."""

from __future__ import annotations

from pathlib import Path
import re
from tempfile import TemporaryDirectory
from typing import Any, Callable

from base_agent_system.config import Settings
from base_agent_system.checkpointing import build_postgres_checkpointer
from base_agent_system.extensions.registry import ExtensionRegistry, create_default_registry
from base_agent_system.memory.graphiti_service import GraphitiMemoryBackend
from base_agent_system.ingestion.pipeline import ingest_markdown_directory
from base_agent_system.memory.graphiti_service import GraphitiMemoryService
from base_agent_system.memory.models import MemoryEpisode
from base_agent_system.retrieval.index_service import RetrievalIndex, build_or_load_index
from base_agent_system.retrieval.models import RetrievalResult
from base_agent_system.workflow.graph import build_workflow

RetrievalServiceFactory = Callable[[Settings], tuple["_MutableRetrievalService", TemporaryDirectory[str]]]
MemoryServiceFactory = Callable[[Settings], GraphitiMemoryService]
IngestServiceFactory = Callable[..., "IngestService"]
WorkflowServiceFactory = Callable[..., "WorkflowService"]


def build_runtime_services(
    settings: Settings,
    *,
    memory_backend: GraphitiMemoryBackend | None = None,
    extension_registry: ExtensionRegistry | None = None,
    retrieval_service_factory: RetrievalServiceFactory | None = None,
    memory_service_factory: Callable[..., GraphitiMemoryService] | None = None,
    ingest_service_factory: IngestServiceFactory | None = None,
    workflow_service_factory: WorkflowServiceFactory | None = None,
) -> tuple[object, object]:
    registry = extension_registry or create_default_registry(settings)
    retrieval_builder = retrieval_service_factory or build_retrieval_service
    memory_builder = memory_service_factory or build_memory_service
    ingest_builder = ingest_service_factory or build_ingest_service
    workflow_builder_factory = workflow_service_factory or build_workflow_service

    retrieval_service, temp_dir = retrieval_builder(settings)
    memory_service = memory_builder(
        settings,
        memory_backend=memory_backend,
    )
    ingest_service = ingest_builder(
        settings,
        retrieval_service=retrieval_service,
        index_dir=getattr(temp_dir, "name", temp_dir),
        connector=registry.get_ingestion_connector("markdown"),
    )
    ingest_service.run(path=str(settings.docs_seed_path))
    workflow_service = workflow_builder_factory(
        settings,
        retrieval_service=retrieval_service,
        memory_service=memory_service,
        temp_dir=temp_dir,
        workflow_builder=registry.get_workflow_builder("default"),
    )
    return ingest_service, workflow_service


def build_retrieval_service(settings: Settings) -> tuple["_MutableRetrievalService", TemporaryDirectory[str]]:
    del settings
    temp_dir = TemporaryDirectory(prefix="base-agent-system-index-")
    return _MutableRetrievalService(), temp_dir


def build_memory_service(
    settings: Settings,
    *,
    memory_backend: GraphitiMemoryBackend | None = None,
) -> GraphitiMemoryService:
    service = GraphitiMemoryService(
        settings=settings,
        backend=memory_backend,
    )
    service.initialize_indices()
    return service


def build_ingest_service(
    settings: Settings,
    *,
    retrieval_service: "_MutableRetrievalService",
    index_dir: str | Path,
    connector: object | None = None,
) -> "IngestService":
    return IngestService(
        settings=settings,
        retrieval_service=retrieval_service,
        index_dir=Path(index_dir),
        connector=connector,
    )


def build_workflow_service(
    settings: Settings,
    *,
    retrieval_service: "_MutableRetrievalService",
    memory_service: GraphitiMemoryService,
    temp_dir: TemporaryDirectory[str],
    workflow_builder: object = build_workflow,
) -> "WorkflowService":
    return WorkflowService(
        settings=settings,
        retrieval_service=retrieval_service,
        memory_service=memory_service,
        temp_dir=temp_dir,
        workflow_builder=workflow_builder,
    )


class IngestService:
    def __init__(
        self,
        *,
        settings: Settings,
        retrieval_service: "_MutableRetrievalService",
        index_dir: Path,
        connector: object,
    ) -> None:
        self._settings = settings
        self._retrieval_service = retrieval_service
        self._index_dir = index_dir
        self._connector = connector

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
        workflow_builder: object,
    ) -> None:
        self._memory_service = memory_service
        self._temp_dir = temp_dir
        self._checkpointer = None
        self._checkpointer_holder = None
        if settings.postgres_uri:
            self._checkpointer_holder = build_postgres_checkpointer(settings.postgres_uri)
        if self._checkpointer_holder is not None:
            self._checkpointer = self._checkpointer_holder.open()
        self._app = workflow_builder(
            settings=settings,
            retrieval_service=retrieval_service,
            memory_service=memory_service,
            checkpointer=self._checkpointer,
        )

    def run(
        self,
        *,
        thread_id: str,
        messages: list[dict[str, str]] | None = None,
        query: str | None = None,
    ) -> dict[str, Any]:
        normalized_messages = messages or _messages_from_query(query)
        latest_user_message = _latest_user_message_text(normalized_messages)
        invoke_kwargs: dict[str, Any] = {}
        if self._checkpointer is not None:
            invoke_kwargs["config"] = {"configurable": {"thread_id": thread_id}}

        result = self._app.invoke(
            {
                "thread_id": thread_id,
                "messages": normalized_messages,
                "query": latest_user_message,
            },
            **invoke_kwargs,
        )
        self._persist_conversation_turns(
            thread_id=thread_id,
            messages=normalized_messages,
            answer=result["answer"],
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

    def _persist_conversation_turns(
        self,
        *,
        thread_id: str,
        messages: list[dict[str, str]],
        answer: str,
    ) -> None:
        latest_user_message = _latest_user_message_text(messages)
        if latest_user_message:
            self._memory_service.store_episode(
                MemoryEpisode(
                    thread_id=thread_id,
                    actor="user",
                    content=latest_user_message,
                )
            )
        if answer.strip():
            self._memory_service.store_episode(
                MemoryEpisode(
                    thread_id=thread_id,
                    actor="assistant",
                    content=answer,
                )
            )


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


def _latest_user_message_text(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content", "").strip()
        if content:
            return content
    return ""


def _messages_from_query(query: str | None) -> list[dict[str, str]]:
    if not query or not query.strip():
        return []
    return [{"role": "user", "content": query.strip()}]

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
