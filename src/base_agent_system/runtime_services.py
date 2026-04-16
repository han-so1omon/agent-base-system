"""Minimal shared runtime services for ingest and query flows."""

from __future__ import annotations

from pathlib import Path
import asyncio
import os
import re
from tempfile import TemporaryDirectory
from typing import Any, Callable

from langchain_openai import ChatOpenAI

from base_agent_system.config import Settings
from base_agent_system.checkpointing import build_postgres_checkpointer
from base_agent_system.extensions.registry import ExtensionRegistry, create_default_registry
from base_agent_system.interactions.repository import InMemoryInteractionRepository, PostgresInteractionRepository
from base_agent_system.memory.graphiti_service import GraphitiMemoryBackend
from base_agent_system.ingestion.pipeline import ingest_markdown_directory
from base_agent_system.memory.graphiti_service import GraphitiMemoryService
from base_agent_system.memory.models import MemoryEpisode
from base_agent_system.observability import (
    NoopObservabilityService,
    ObservabilityService,
)
from base_agent_system.retrieval.index_service import RetrievalIndex, build_or_load_index
from base_agent_system.retrieval.models import RetrievalResult
from base_agent_system.workflow.graph import build_workflow

RetrievalServiceFactory = Callable[[Settings], tuple["_MutableRetrievalService", TemporaryDirectory[str]]]
MemoryServiceFactory = Callable[[Settings], GraphitiMemoryService]
IngestServiceFactory = Callable[..., "IngestService"]
WorkflowServiceFactory = Callable[..., "WorkflowService"]
TopicPreviewGenerator = Callable[[str], str]


def build_runtime_services(
    settings: Settings,
    *,
    memory_backend: GraphitiMemoryBackend | None = None,
    extension_registry: ExtensionRegistry | None = None,
    retrieval_service_factory: RetrievalServiceFactory | None = None,
    memory_service_factory: Callable[..., GraphitiMemoryService] | None = None,
    ingest_service_factory: IngestServiceFactory | None = None,
    workflow_service_factory: WorkflowServiceFactory | None = None,
    observability_service: ObservabilityService | None = None,
) -> tuple[object, object, object]:
    registry = extension_registry or create_default_registry(settings)
    retrieval_builder = retrieval_service_factory or build_retrieval_service
    memory_builder = memory_service_factory or build_memory_service
    ingest_builder = ingest_service_factory or build_ingest_service
    workflow_builder_factory = workflow_service_factory or build_workflow_service
    obs_service = observability_service or NoopObservabilityService()

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
    interaction_repository = (
        InMemoryInteractionRepository()
        if memory_backend is not None
        else PostgresInteractionRepository(postgres_uri=settings.postgres_uri)
    )
    interaction_repository.initialize_schema()
    workflow_service = workflow_builder_factory(
        settings,
        retrieval_service=retrieval_service,
        memory_service=memory_service,
        temp_dir=temp_dir,
        workflow_builder=registry.get_workflow_builder("default"),
        interaction_repository=interaction_repository,
        observability_service=obs_service,
        topic_preview_generator=(lambda text: "Generated topic") if memory_backend is not None else _build_topic_preview_generator(settings),
    )
    return ingest_service, workflow_service, interaction_repository


class _InMemoryGraphitiBackend(GraphitiMemoryBackend):
    def initialize_indices(self) -> None:
        pass

    def store_episode(self, episode: Any) -> None:
        pass

    def search_memory(self, query: str, *, thread_id: str) -> list[Any]:
        return []


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
    interaction_repository: object,
    workflow_builder: object = build_workflow,
    observability_service: ObservabilityService | None = None,
    topic_preview_generator: TopicPreviewGenerator | None = None,
) -> "WorkflowService":
    return WorkflowService(
        settings=settings,
        retrieval_service=retrieval_service,
        memory_service=memory_service,
        temp_dir=temp_dir,
        interaction_repository=interaction_repository,
        topic_preview_generator=topic_preview_generator,
        workflow_builder=workflow_builder,
        observability_service=observability_service,
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
        interaction_repository: object,
        workflow_builder: object,
        observability_service: ObservabilityService | None = None,
        topic_preview_generator: TopicPreviewGenerator | None = None,
    ) -> None:
        self._memory_service = memory_service
        self._temp_dir = temp_dir
        self._interaction_repository = interaction_repository
        self._observability_service = observability_service or NoopObservabilityService()
        self._topic_preview_generator = topic_preview_generator or (lambda text: "Generated topic")
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
        return asyncio.run(self.arun(thread_id=thread_id, messages=messages, query=query))

    async def arun(
        self,
        *,
        thread_id: str,
        interaction_id: str | None = None,
        parent_interaction_id: str | None = None,
        messages: list[dict[str, str]] | None = None,
        query: str | None = None,
    ) -> dict[str, Any]:
        with self._observability_service.start_branch_trace(
            thread_id=thread_id,
            interaction_id=interaction_id or "",
            parent_interaction_id=parent_interaction_id,
        ) as trace:
            normalized_messages = messages or _messages_from_query(query)
            latest_user_message = _latest_user_message_text(normalized_messages)
            invoke_kwargs: dict[str, Any] = {}
            if self._checkpointer is not None:
                invoke_kwargs["config"] = {"configurable": {"thread_id": thread_id}}

            payload = {
                "thread_id": thread_id,
                "messages": normalized_messages,
                "query": latest_user_message,
                "interaction_id": interaction_id,
                "parent_interaction_id": parent_interaction_id,
            }
            with self._observability_service.start_span(
                name="workflow_invoke",
                metadata={"thread_id": thread_id, "interaction_id": interaction_id or ""},
            ):
                if hasattr(self._app, "ainvoke"):
                    result = await self._app.ainvoke(payload, **invoke_kwargs)
                else:
                    result = self._app.invoke(payload, **invoke_kwargs)

            trace.update_metadata(
                {
                    "used_tools": result.get("interaction", {}).get("used_tools", False),
                    "tool_call_count": result.get("interaction", {}).get(
                        "tool_call_count", 0
                    ),
                    "citation_count": len(result.get("citations", [])),
                }
            )

            with self._observability_service.start_span(
                name="persist_conversation_turns",
                metadata={"thread_id": thread_id},
            ):
                await self._persist_conversation_turns(
                    thread_id=thread_id,
                    messages=normalized_messages,
                    answer=result["answer"],
                )
            with self._observability_service.start_span(
                name="persist_interactions",
                metadata={"thread_id": thread_id, "interaction_id": interaction_id or ""},
            ):
                self._persist_interactions(
                    thread_id=thread_id,
                    messages=normalized_messages,
                    answer=result["answer"],
                    interaction=result.get("interaction", {}),
                    interaction_id=interaction_id,
                    parent_interaction_id=parent_interaction_id,
                )
        self._observability_service.flush()
        return {
            "thread_id": result["thread_id"],
            "answer": result["answer"],
            "citations": result["citations"],
            "debug": result["debug"],
            "interaction": result.get("interaction", {}),
        }

    def close(self) -> None:
        self._memory_service.close()
        if self._checkpointer_holder is not None:
            self._checkpointer_holder.close()
            self._checkpointer = None
        self._temp_dir.cleanup()

    async def _persist_conversation_turns(
        self,
        *,
        thread_id: str,
        messages: list[dict[str, str]],
        answer: str,
    ) -> None:
        latest_user_message = _latest_user_message_text(messages)
        if latest_user_message:
            topic_preview = None
            is_new_thread = not self._interaction_repository.has_thread(thread_id=thread_id)
            if is_new_thread:
                try:
                    topic_preview = _require_topic_preview(self._topic_preview_generator, latest_user_message)
                except Exception as exc:
                    import logging
                    logging.getLogger(__name__).warning("failed to generate topic preview: %s", exc)
                    raise ValueError(f"Topic preview generation failed: {exc}") from exc

            if hasattr(self._interaction_repository, "create_interaction") and hasattr(self._interaction_repository, "append_event"):
                user_interaction = self._interaction_repository.create_interaction(
                    thread_id=thread_id,
                    kind="user",
                    status="completed",
                    metadata={"topic_preview": topic_preview} if topic_preview else None,
                )
                self._interaction_repository.append_event(
                    interaction_id=user_interaction.id,
                    event_type="message_authored",
                    content=latest_user_message,
                    is_display_event=True,
                    status="completed",
                )
            else:
                self._interaction_repository.store_user_interaction(
                    thread_id=thread_id,
                    content=latest_user_message,
                    topic_preview=topic_preview,
                )

            await self._store_memory_episode(
                MemoryEpisode(thread_id=thread_id, actor="user", content=latest_user_message)
            )

        if answer.strip():
            await self._store_memory_episode(
                MemoryEpisode(thread_id=thread_id, actor="assistant", content=answer)
            )

    async def _store_memory_episode(self, episode: MemoryEpisode) -> None:
        if hasattr(self._memory_service, "astore_episode"):
            await self._memory_service.astore_episode(episode)
        else:
            self._memory_service.store_episode(episode)

    def _persist_interactions(
        self,
        *,
        thread_id: str,
        messages: list[dict[str, str]],
        answer: str,
        interaction: dict[str, Any],
        interaction_id: str | None = None,
        parent_interaction_id: str | None = None,
    ) -> None:
        if answer.strip():
            if hasattr(self._interaction_repository, "create_interaction") and hasattr(self._interaction_repository, "append_event"):
                agent_interaction_id = interaction_id
                if agent_interaction_id is None:
                    agent_interaction = self._interaction_repository.create_interaction(
                        thread_id=thread_id,
                        parent_interaction_id=parent_interaction_id,
                        kind="agent_run",
                        status="completed",
                        metadata={
                            "used_tools": bool(interaction.get("used_tools", False)),
                            "tool_call_count": int(interaction.get("tool_call_count", 0)),
                            "tools_used": list(interaction.get("tools_used", [])),
                            "steps": list(interaction.get("steps", [])),
                            **({"spawn": interaction["spawn"]} if "spawn" in interaction else {}),
                        },
                    )
                    agent_interaction_id = agent_interaction.id
                else:
                    # Update existing interaction metadata if we have it
                    if hasattr(self._interaction_repository, "update_interaction_metadata"):
                         self._interaction_repository.update_interaction_metadata(
                             interaction_id=agent_interaction_id,
                             metadata={
                                 "used_tools": bool(interaction.get("used_tools", False)),
                                 "tool_call_count": int(interaction.get("tool_call_count", 0)),
                                 "tools_used": list(interaction.get("tools_used", [])),
                                 "steps": list(interaction.get("steps", [])),
                                 **({"spawn": interaction["spawn"]} if "spawn" in interaction else {}),
                             }
                         )

                self._interaction_repository.append_event(
                    interaction_id=agent_interaction_id,
                    event_type="message_authored",
                    content=answer,
                    is_display_event=True,
                    status="completed",
                    artifacts=list(interaction.get("artifacts", [])),
                )
                self._interaction_repository.append_event(
                    interaction_id=agent_interaction_id,
                    event_type="tool_summary",
                    status="completed",
                    metadata={"steps": list(interaction.get("steps", []))},
                )
            else:
                self._interaction_repository.store_agent_run_interaction(
                    thread_id=thread_id,
                    content=answer,
                    tool_call_count=int(interaction.get("tool_call_count", 0)),
                    tools_used=list(interaction.get("tools_used", [])),
                    steps=list(interaction.get("steps", [])),
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


def _build_topic_preview_generator(settings: Settings) -> TopicPreviewGenerator:
    model = ChatOpenAI(
        model=settings.openai_model,
        api_key=os.getenv(settings.openai_api_key_name, "") or "missing-api-key",
    )

    def generate(text: str) -> str:
        result = model.invoke(
            [
                (
                    "system",
                    "Return a concise thread topic title for the user's first message. Use plain text only, 2 to 5 words maximum, and do not simply repeat the opening words verbatim.",
                ),
                ("human", text),
            ]
        )
        return _normalize_topic_preview(_extract_llm_text(getattr(result, "content", "")), source_text=text)

    return generate


def _require_topic_preview(generator: TopicPreviewGenerator, text: str) -> str:
    return _normalize_topic_preview(generator(text), source_text=text)


def _normalize_topic_preview(value: str, *, source_text: str) -> str:
    candidate = value.strip().strip(".,:;!?-\"'`()[]{}")
    words = re.findall(r"[A-Za-z0-9']+", candidate)
    if not words:
        raise ValueError("topic preview generation failed: empty output")
    if not 2 <= len(words) <= 5:
        raise ValueError("topic preview generation failed: topic preview must be 2 to 5 words")
    source_words = re.findall(r"[A-Za-z0-9']+", source_text.lower())
    opening_words = source_words[: len(words)]
    if opening_words and [word.lower() for word in words] == opening_words:
        raise ValueError("topic preview generation failed: topic preview repeats opening words")
    return " ".join(words)


def _messages_from_query(query: str | None) -> list[dict[str, str]]:
    if not query:
        return []
    return [{"role": "user", "content": query}]


def _latest_user_message_text(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content", "")
    return ""


def _extract_llm_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        )
    return str(content)
