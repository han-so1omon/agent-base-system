from __future__ import annotations

import pytest

from base_agent_system.config import Settings
from base_agent_system.memory.models import MemoryEpisode, MemorySearchResult
from base_agent_system.runtime_services import (
    WorkflowService,
    _InMemoryGraphitiBackend,
    build_ingest_service,
    build_memory_service,
    build_retrieval_service,
    build_runtime_services,
    build_workflow_service,
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


def test_workflow_supports_constrained_hooks_around_retrieval_and_synthesis() -> None:
    events: list[str] = []
    retrieval = _StubRetrievalService(
        [
            RetrievalResult(
                text="Base context from docs.",
                score=1.0,
                citation=Citation(
                    path="docs/seed/example.md",
                    snippet="Base context from docs.",
                ),
            )
        ]
    )
    memory = _StubMemoryService(
        [
            MemorySearchResult(
                thread_id="thread-hooks",
                actor="user",
                content="Remembered preference.",
                score=1.0,
            )
        ]
    )

    workflow = build_workflow(
        settings=_settings(),
        retrieval_service=retrieval,
        memory_service=memory,
        workflow_hooks={
            "before_retrieval": (_record_hook("before_retrieval", events),),
            "after_retrieval": (_add_debug_flag_hook("after_retrieval", events),),
            "before_answer_synthesis": (_record_hook("before_answer_synthesis", events),),
            "after_answer_synthesis": (
                _append_answer_hook("after_answer_synthesis", events, " Hooked."),
            ),
        },
        state_graph_factory=lambda state_type: _FakeStateGraph(),
    )

    result = workflow.invoke({"thread_id": "thread-hooks", "query": "What context is available?"})

    assert events == [
        "before_retrieval",
        "after_retrieval",
        "before_answer_synthesis",
        "after_answer_synthesis",
    ]
    assert result["debug"]["after_retrieval"] == 1
    assert result["answer"].endswith("Hooked.")


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
        workflow_builder=fake_build_workflow,
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


def test_runtime_service_factories_build_individual_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

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

    retrieval_service, temp_dir = build_retrieval_service(_settings())
    memory_service = build_memory_service(_settings(), memory_backend=_InMemoryGraphitiBackend())
    ingest_service = build_ingest_service(
        _settings(),
        retrieval_service=retrieval_service,
        index_dir=temp_dir.name,
    )
    workflow_service = build_workflow_service(
        _settings(),
        retrieval_service=retrieval_service,
        memory_service=memory_service,
        temp_dir=temp_dir,
    )

    result = ingest_service.run(path="docs/seed")

    assert result["file_count"] >= 1
    assert workflow_service is not None
    workflow_service.close()


def test_build_runtime_services_accepts_custom_service_factories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_retrieval_factory(settings):
        observed["retrieval_settings"] = settings
        return _StubRetrievalService([]), _TempDir()

    def fake_memory_factory(settings, *, memory_backend=None):
        observed["memory_settings"] = settings
        observed["memory_backend"] = memory_backend
        return _StubMemoryService([])

    def fake_ingest_factory(settings, *, retrieval_service, index_dir, connector=None):
        observed["ingest_settings"] = settings
        observed["ingest_retrieval_service"] = retrieval_service
        observed["ingest_index_dir"] = index_dir
        observed["ingest_connector"] = connector
        return _StubIngestService()

    def fake_workflow_factory(settings, *, retrieval_service, memory_service, temp_dir, workflow_builder):
        observed["workflow_settings"] = settings
        observed["workflow_retrieval_service"] = retrieval_service
        observed["workflow_memory_service"] = memory_service
        observed["workflow_temp_dir"] = temp_dir
        observed["workflow_builder"] = workflow_builder
        return _StubWorkflowService()

    ingest_service, workflow_service = build_runtime_services(
        _settings(),
        memory_backend=_InMemoryGraphitiBackend(),
        retrieval_service_factory=fake_retrieval_factory,
        memory_service_factory=fake_memory_factory,
        ingest_service_factory=fake_ingest_factory,
        workflow_service_factory=fake_workflow_factory,
    )

    assert isinstance(ingest_service, _StubIngestService)
    assert isinstance(workflow_service, _StubWorkflowService)
    assert observed["retrieval_settings"] == _settings()
    assert observed["memory_settings"] == _settings()
    assert observed["ingest_settings"] == _settings()
    assert observed["workflow_settings"] == _settings()


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


class _StubIngestService:
    def run(self, *, path: str | None = None) -> dict[str, int]:
        return {"file_count": 0, "chunk_count": 0}


class _StubWorkflowService:
    def run(self, *, thread_id: str, query: str) -> dict[str, object]:
        return {
            "thread_id": thread_id,
            "answer": query,
            "citations": [],
            "debug": {"document_hits": 0, "memory_hits": 0},
        }

    def close(self) -> None:
        return None


def _record_hook(name: str, events: list[str]):
    def hook(state: dict[str, object]) -> dict[str, object]:
        events.append(name)
        return {}

    return hook


def _add_debug_flag_hook(name: str, events: list[str]):
    def hook(state: dict[str, object]) -> dict[str, object]:
        events.append(name)
        debug = dict(state.get("debug", {}))
        debug[name] = 1
        return {"debug": debug}

    return hook


def _append_answer_hook(name: str, events: list[str], suffix: str):
    def hook(state: dict[str, object]) -> dict[str, object]:
        events.append(name)
        return {"answer": f"{state['answer']}{suffix}"}

    return hook


class _FakeStateGraph:
    def __init__(self) -> None:
        self._nodes: dict[str, object] = {}
        self._edges: list[tuple[str, str]] = []

    def add_node(self, name: str, node: object) -> None:
        self._nodes[name] = node

    def add_edge(self, start: str, end: str) -> None:
        self._edges.append((start, end))

    def compile(self, *, checkpointer: object | None = None) -> _CompiledWorkflow:
        return _CompiledWorkflow(self._nodes, self._edges)


class _CompiledWorkflow:
    def __init__(self, nodes: dict[str, object], edges: list[tuple[str, str]]) -> None:
        self._nodes = nodes
        self._edges = edges

    def invoke(self, state: dict[str, object]) -> dict[str, object]:
        current_state = dict(state)
        node_name = self._next_node("START")
        while node_name != "END":
            update = self._nodes[node_name](current_state)
            current_state.update(update)
            node_name = self._next_node(node_name)
        return current_state

    def _next_node(self, start: str) -> str:
        for edge_start, edge_end in self._edges:
            if edge_start == start:
                return edge_end
        raise AssertionError(f"missing edge from {start}")


class _TempDir:
    def cleanup(self) -> None:
        return None
