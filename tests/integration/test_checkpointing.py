from __future__ import annotations

from types import SimpleNamespace

import pytest

from base_agent_system.checkpointing import build_postgres_checkpointer
from base_agent_system.config import Settings
from base_agent_system.workflow.graph import build_workflow


def _settings() -> Settings:
    return Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        neo4j_database="neo4j",
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
    )


def test_build_postgres_checkpointer_calls_setup_on_created_saver() -> None:
    created: list[_FakePostgresSaver] = []

    def saver_factory(uri: str) -> _ContextManager:
        saver = _FakePostgresSaver(uri)
        created.append(saver)
        return _ContextManager(saver)

    holder = build_postgres_checkpointer(
        _settings().postgres_uri,
        saver_factory=saver_factory,
    )

    saver = holder.open()
    same_saver = holder.open()

    assert saver is created[0]
    assert same_saver is saver
    assert saver.connection_uri == _settings().postgres_uri
    assert saver.setup_calls == 1

    holder.close()


def test_build_postgres_checkpointer_returns_holder_with_installed_dependency() -> None:
    holder = build_postgres_checkpointer(_settings().postgres_uri)

    assert holder is not None


def test_workflow_passes_checkpointer_to_langgraph_compile() -> None:
    compile_calls: list[object] = []

    app = build_workflow(
        settings=_settings(),
        retrieval_service=_StubRetrievalService(),
        memory_service=_StubMemoryService(),
        checkpointer=SimpleNamespace(name="checkpoint"),
        state_graph_factory=lambda state_type: _FakeStateGraph(compile_calls),
    )

    assert app == "compiled-app"
    assert compile_calls == [SimpleNamespace(name="checkpoint")]


class _FakePostgresSaver:
    def __init__(self, connection_uri: str) -> None:
        self.connection_uri = connection_uri
        self.setup_calls = 0

    def setup(self) -> None:
        self.setup_calls += 1


class _ContextManager:
    def __init__(self, saver: _FakePostgresSaver) -> None:
        self._saver = saver

    def __enter__(self) -> _FakePostgresSaver:
        return self._saver

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeStateGraph:
    def __init__(self, compile_calls: list[object]) -> None:
        self._compile_calls = compile_calls

    def add_node(self, name: str, node: object) -> None:
        return None

    def add_edge(self, start: str, end: str) -> None:
        return None

    def compile(self, *, checkpointer: object | None = None) -> str:
        self._compile_calls.append(checkpointer)
        return "compiled-app"


class _StubRetrievalService:
    def query(self, text: str, *, top_k: int) -> list[object]:
        return []


class _StubMemoryService:
    def search_memory(self, query: str, *, thread_id: str, limit: int = 5) -> list[object]:
        return []

    def store_episode(self, episode: object) -> None:
        return None
