from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from base_agent_system.interactions.repository import InMemoryInteractionRepository
from base_agent_system.runtime_services import _InMemoryGraphitiBackend


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv(
        "BASE_AGENT_SYSTEM_POSTGRES_URI",
        "postgresql://postgres:postgres@localhost:5432/app",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")


def test_get_threads_returns_thread_summaries(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    from base_agent_system.api.app import create_app

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    app = create_app(initialize_dependencies=False, memory_backend=_InMemoryGraphitiBackend())

    with TestClient(app) as client:
        client.app.state.runtime_state.interaction_repository = _StubInteractionRepository()
        response = client.get("/threads?limit=50")

    assert response.status_code == 200
    assert response.json() == [{"thread_id": "thread-123", "preview": "Seed doc summary"}]


def test_get_thread_interactions_returns_visible_interactions(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    from base_agent_system.api.app import create_app

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    app = create_app(initialize_dependencies=False, memory_backend=_InMemoryGraphitiBackend())

    with TestClient(app) as client:
        client.app.state.runtime_state.interaction_repository = _StubInteractionRepository()
        response = client.get("/threads/thread-123/interactions?limit=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["messages"][0]["kind"] == "user"
    assert payload["messages"][1]["kind"] == "agent_run"
    assert payload["messages"][1]["metadata"]["used_tools"] is True
    assert payload["messages"][1]["metadata"]["tool_call_count"] == 2
    assert payload["messages"][1]["metadata"]["tools_used"] == ["search_docs", "search_memory"]


def test_get_thread_interactions_maps_real_repository_page_items(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    from base_agent_system.api.app import create_app

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    repository = InMemoryInteractionRepository()
    repository.store_user_interaction(thread_id="thread-123", content="What does the seed doc say?")
    repository.store_agent_run_interaction(
        thread_id="thread-123",
        content="The seed doc explains markdown ingestion.",
        tool_call_count=1,
        tools_used=["search_docs"],
        steps=[],
        intermediate_reasoning=None,
    )

    app = create_app(initialize_dependencies=False, memory_backend=_InMemoryGraphitiBackend())

    with TestClient(app) as client:
        client.app.state.runtime_state.interaction_repository = repository
        response = client.get("/threads/thread-123/interactions?limit=20")

    assert response.status_code == 200
    payload = response.json()
    assert [message["kind"] for message in payload["messages"]] == ["user", "agent_run"]
    assert payload["messages"][1]["metadata"]["tool_call_count"] == 1


def test_get_threads_maps_real_repository_summaries(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    from base_agent_system.api.app import create_app

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    repository = InMemoryInteractionRepository()
    repository.store_user_interaction(thread_id="thread-123", content="What does the seed doc say?", topic_preview="Seed doc summary")

    app = create_app(initialize_dependencies=False, memory_backend=_InMemoryGraphitiBackend())

    with TestClient(app) as client:
        client.app.state.runtime_state.interaction_repository = repository
        response = client.get("/threads?limit=50")

    assert response.status_code == 200
    assert response.json() == [{"thread_id": "thread-123", "preview": "Seed doc summary"}]


def test_get_threads_excludes_threads_without_stored_previews(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    from base_agent_system.api.app import create_app

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    repository = InMemoryInteractionRepository()
    repository.store_user_interaction(thread_id="thread-123", content="What does the seed doc say?")

    app = create_app(initialize_dependencies=False, memory_backend=_InMemoryGraphitiBackend())

    with TestClient(app) as client:
        client.app.state.runtime_state.interaction_repository = repository
        response = client.get("/threads?limit=50")

    assert response.status_code == 200
    assert response.json() == []


def test_debug_interaction_endpoint_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    from base_agent_system.api.app import create_app

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    app = create_app(initialize_dependencies=False, memory_backend=_InMemoryGraphitiBackend())

    with TestClient(app) as client:
        client.app.state.runtime_state.interaction_repository = _StubInteractionRepository()
        response = client.get("/debug/threads/thread-123/interactions/interaction-agent-1")

    assert response.status_code == 404


class _StubInteractionRepository:
    def list_threads(self, *, limit: int):
        return [
            {
                "thread_id": "thread-123",
                "preview": "Seed doc summary",
            }
        ]

    def list_interactions(self, *, thread_id: str, limit: int, before_ts=None, before_id=None):
        return {
            "messages": [
                {
                    "id": "interaction-user-1",
                    "thread_id": thread_id,
                    "kind": "user",
                    "content": "What does the seed doc say?",
                    "created_at": "2026-04-08T00:00:00Z",
                    "metadata": None,
                },
                {
                    "id": "interaction-agent-1",
                    "thread_id": thread_id,
                    "kind": "agent_run",
                    "content": "The seed doc explains markdown ingestion.",
                    "created_at": "2026-04-08T00:00:01Z",
                    "metadata": {
                        "used_tools": True,
                        "tool_call_count": 2,
                        "tools_used": ["search_docs", "search_memory"],
                    },
                },
            ],
            "has_more": False,
            "next_before": None,
        }

    def get_debug_interaction(self, *, thread_id: str, interaction_id: str):
        return {
            "thread_id": thread_id,
            "interaction_id": interaction_id,
            "steps": [],
            "reasoning": {"kind": "chain_of_thought", "content": "internal"},
        }
