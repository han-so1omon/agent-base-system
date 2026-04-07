from __future__ import annotations

import pytest

from base_agent_system.config import Settings
from base_agent_system.memory.models import MemoryEpisode, MemorySearchResult
from base_agent_system.runtime_services import (
    WorkflowService,
    _InMemoryGraphitiBackend,
    build_runtime_services,
)
from base_agent_system.retrieval.models import Citation, RetrievalResult
from base_agent_system.workflow.graph import build_workflow


def _settings() -> Settings:
    return Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        neo4j_database="neo4j",
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
    )


def test_workflow_retrieves_docs_and_memory_then_returns_answer_and_citations() -> None:
    retrieval = _StubRetrievalService(
        [
            RetrievalResult(
                text="The seed docs say the system uses markdown ingestion for local context.",
                score=1.0,
                citation=Citation(
                    path="docs/seed/example.md",
                    snippet="markdown ingestion for local context",
                ),
            )
        ]
    )
    memory = _StubMemoryService(
        [
            MemorySearchResult(
                thread_id="thread-123",
                actor="user",
                content="I prefer concise answers.",
                score=1.0,
            )
        ]
    )
    workflow = build_workflow(
        settings=_settings(),
        retrieval_service=retrieval,
        memory_service=memory,
        state_graph_factory=lambda state_type: _FakeStateGraph(),
    )

    result = workflow.invoke({"thread_id": "thread-123", "query": "How does this system get context?"})

    assert retrieval.queries == ["How does this system get context?"]
    assert memory.search_calls == [("How does this system get context?", "thread-123", 3)]
    assert memory.stored_episodes == [
        MemoryEpisode(
            thread_id="thread-123",
            actor="user",
            content="How does this system get context?",
        ),
        MemoryEpisode(
            thread_id="thread-123",
            actor="assistant",
            content=result["answer"],
        ),
    ]
    assert len(result["retrieved_docs"]) == 1
    assert len(result["retrieved_memory"]) == 1
    assert result["citations"] == [
        {
            "source": "docs/seed/example.md",
            "snippet": "markdown ingestion for local context",
        }
    ]
    assert "markdown ingestion" in result["answer"].lower()
    assert "concise answers" in result["answer"].lower()
    assert result["debug"] == {"document_hits": 1, "memory_hits": 1}


def test_workflow_builds_with_langgraph_when_dependency_is_available() -> None:
    app = build_workflow(
        settings=_settings(),
        retrieval_service=_StubRetrievalService([]),
        memory_service=_StubMemoryService([]),
    )

    assert hasattr(app, "invoke")


def test_runtime_workflow_service_delegates_to_real_workflow_builder(monkeypatch: pytest.MonkeyPatch) -> None:
    built_with: dict[str, object] = {}
    opened_checkpointer = object()

    class _WorkflowApp:
        def invoke(self, state: dict[str, object], **kwargs) -> dict[str, object]:
            return {
                **state,
                "answer": "ok",
                "citations": [],
                "debug": {"document_hits": 0, "memory_hits": 0},
            }

    def fake_build_workflow(**kwargs):
        built_with.update(kwargs)
        return _WorkflowApp()

    class _CheckpointerHolder:
        def open(self) -> object:
            return opened_checkpointer

        def close(self) -> None:
            return None

    monkeypatch.setattr("base_agent_system.runtime_services.build_workflow", fake_build_workflow)
    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    service = WorkflowService(
        settings=_settings(),
        retrieval_service=_StubRetrievalService([]),
        memory_service=_StubMemoryService([]),
        temp_dir=_TempDir(),
    )

    result = service.run(thread_id="thread-1", query="hello")

    assert built_with["settings"] == _settings()
    assert "state_graph_factory" not in built_with
    assert built_with["checkpointer"] is opened_checkpointer
    assert result["answer"] == "ok"


def test_build_runtime_services_bootstraps_docs_seed_retrieval_on_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    backend = _InMemoryGraphitiBackend()

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    def fake_initialize(self) -> None:
        if self._backend is not None and hasattr(self._backend, "initialize_indices"):
            self._backend.initialize_indices()
        self._initialized = True

    monkeypatch.setattr(
        "base_agent_system.memory.graphiti_service.GraphitiMemoryService.initialize_indices",
        fake_initialize,
    )
    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    ingest_service, workflow_service = build_runtime_services(
        _settings(),
        memory_backend=backend,
    )

    result = workflow_service.run(
        thread_id="thread-bootstrap",
        query="What does the seed document explain?",
    )

    assert result["debug"]["document_hits"] >= 1
    assert result["citations"]
    assert result["citations"][0]["source"].endswith("docs/seed/example.md")

    workflow_service.close()


def test_build_runtime_services_prefers_live_graphiti_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    observed: dict[str, object] = {}

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    def fake_initialize(self) -> None:
        observed["backend"] = self._backend
        self._initialized = True

    monkeypatch.setattr(
        "base_agent_system.memory.graphiti_service.GraphitiMemoryService.initialize_indices",
        fake_initialize,
    )
    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    ingest_service, workflow_service = build_runtime_services(_settings())

    assert observed["backend"] is None
    workflow_service.close()


def test_build_runtime_services_uses_explicit_in_memory_backend_for_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    observed: dict[str, object] = {}

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    def fake_initialize(self) -> None:
        observed["backend"] = self._backend
        self._initialized = True

    monkeypatch.setattr(
        "base_agent_system.memory.graphiti_service.GraphitiMemoryService.initialize_indices",
        fake_initialize,
    )
    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    backend = _InMemoryGraphitiBackend()

    ingest_service, workflow_service = build_runtime_services(
        _settings(),
        memory_backend=backend,
    )

    assert observed["backend"] is backend
    workflow_service.close()


class _StubRetrievalService:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self._results = results
        self.queries: list[str] = []

    def query(self, text: str, *, top_k: int) -> list[RetrievalResult]:
        assert top_k == 3
        self.queries.append(text)
        return self._results


class _StubMemoryService:
    def __init__(self, results: list[MemorySearchResult]) -> None:
        self._results = results
        self.search_calls: list[tuple[str, str, int]] = []
        self.stored_episodes: list[MemoryEpisode] = []

    def search_memory(
        self,
        query: str,
        *,
        thread_id: str,
        limit: int = 5,
    ) -> list[MemorySearchResult]:
        self.search_calls.append((query, thread_id, limit))
        return self._results

    def store_episode(self, episode: MemoryEpisode) -> None:
        self.stored_episodes.append(episode)


class _FakeStateGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, object] = {}
        self._edges: list[tuple[str, str]] = []

    def add_node(self, name: str, node: object) -> None:
        self._nodes[name] = node

    def add_edge(self, start: str, end: str) -> None:
        self._edges.append((start, end))

    def compile(self, *, checkpointer: object | None = None) -> _CompiledWorkflow:
        return _CompiledWorkflow(self._nodes)


class _CompiledWorkflow:
    def __init__(self, nodes: dict[str, object]) -> None:
        self._nodes = nodes

    def invoke(self, state: dict[str, object]) -> dict[str, object]:
        current_state = dict(state)
        for node_name in (
            "retrieve_docs",
            "retrieve_memory",
            "synthesize_answer",
            "persist_memory",
        ):
            update = self._nodes[node_name](current_state)
            current_state.update(update)
        return current_state


class _TempDir:
    def cleanup(self) -> None:
        return None
