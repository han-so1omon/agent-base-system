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
    app = _create_test_app(monkeypatch)

    with TestClient(app) as client:
        client.app.state.runtime_state.interaction_repository = _StubInteractionRepository()
        response = client.get("/threads?limit=50")

    assert response.status_code == 200
    assert response.json() == [{"thread_id": "thread-123", "preview": "Seed doc summary"}]


def test_get_thread_interactions_returns_projected_root_interactions(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)
    app = _create_test_app(monkeypatch)

    with TestClient(app) as client:
        client.app.state.runtime_state.interaction_repository = _StubInteractionRepository()
        response = client.get("/threads/thread-123/interactions?limit=20")

    assert response.status_code == 200
    payload = response.json()
    assert [item["kind"] for item in payload["items"]] == ["user", "agent_run"]
    assert payload["items"][1]["latest_display_event"]["content"] == "I started a deeper investigation."
    assert payload["items"][1]["metadata"]["used_tools"] is True


def test_get_interaction_children_returns_projected_child_interactions(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)
    app = _create_test_app(monkeypatch)

    with TestClient(app) as client:
        client.app.state.runtime_state.interaction_repository = _StubInteractionRepository()
        response = client.get("/interactions/interaction-agent-1/children?limit=20")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["parent_interaction_id"] == "interaction-agent-1"
    assert payload["items"][0]["latest_display_event"]["event_type"] == "queued"


def test_get_interaction_events_returns_event_timeline(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)
    app = _create_test_app(monkeypatch)

    with TestClient(app) as client:
        client.app.state.runtime_state.interaction_repository = _StubInteractionRepository()
        response = client.get("/interactions/interaction-agent-1/events?limit=20")

    assert response.status_code == 200
    payload = response.json()
    assert [item["event_type"] for item in payload["items"]] == ["started", "child_summary"]
    assert payload["items"][1]["metadata"] == {"child_interaction_id": "interaction-child-1"}


def test_get_interaction_events_supports_cancellation_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)
    app = _create_test_app(monkeypatch)
    repository = InMemoryInteractionRepository()
    interaction = repository.create_interaction(thread_id="thread-123", kind="deep_agent", status="running")
    repository.request_cancellation(interaction_id=interaction.id)

    with TestClient(app) as client:
        client.app.state.runtime_state.interaction_repository = repository
        response = client.get(f"/interactions/{interaction.id}/events?limit=20")

    assert response.status_code == 200
    assert response.json()["items"][0]["event_type"] == "cancel_requested"


def test_get_thread_interactions_maps_real_repository_page_items(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)
    app = _create_test_app(monkeypatch)
    repository = InMemoryInteractionRepository()
    root = repository.create_interaction(
        thread_id="thread-123",
        kind="agent_run",
        status="running",
        metadata={"topic_preview": "Seed doc summary"},
    )
    repository.append_event(
        interaction_id=root.id,
        event_type="started",
        content="Investigating request.",
        is_display_event=True,
        status="running",
    )
    child = repository.create_interaction(
        thread_id="thread-123",
        parent_interaction_id=root.id,
        kind="deep_agent",
        status="queued",
    )
    repository.append_event(
        interaction_id=child.id,
        event_type="queued",
        content="Queued child agent.",
        is_display_event=True,
        status="queued",
    )

    with TestClient(app) as client:
        client.app.state.runtime_state.interaction_repository = repository
        interactions_response = client.get("/threads/thread-123/interactions?limit=20")
        children_response = client.get(f"/interactions/{root.id}/children?limit=20")

    assert interactions_response.status_code == 200
    assert children_response.status_code == 200
    assert interactions_response.json()["items"][0]["latest_display_event"]["content"] == "Investigating request."
    assert children_response.json()["items"][0]["latest_display_event"]["content"] == "Queued child agent."


def test_debug_interaction_endpoint_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)
    app = _create_test_app(monkeypatch)

    with TestClient(app) as client:
        client.app.state.runtime_state.interaction_repository = _StubInteractionRepository()
        response = client.get("/debug/threads/thread-123/interactions/interaction-agent-1")

    assert response.status_code == 404


def _create_test_app(monkeypatch: pytest.MonkeyPatch):
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
    return create_app(initialize_dependencies=False, memory_backend=_InMemoryGraphitiBackend())


class _StubInteractionRepository:
    def list_threads(self, *, limit: int):
        return [{"thread_id": "thread-123", "preview": "Seed doc summary"}]

    def list_thread_interactions(self, *, thread_id: str, limit: int, before_ts=None, before_id=None):
        del limit, before_ts, before_id
        return {
            "items": [
                {
                    "id": "interaction-user-1",
                    "thread_id": thread_id,
                    "parent_interaction_id": None,
                    "kind": "user",
                    "status": "completed",
                    "created_at": "2026-04-08T00:00:00Z",
                    "updated_at": "2026-04-08T00:00:00Z",
                    "last_event_at": "2026-04-08T00:00:00Z",
                    "latest_display_event_id": "event-user-1",
                    "child_count": 0,
                    "latest_display_event": {
                        "id": "event-user-1",
                        "interaction_id": "interaction-user-1",
                        "event_type": "message_authored",
                        "created_at": "2026-04-08T00:00:00Z",
                        "content": "What does the seed doc say?",
                        "is_display_event": True,
                        "status": "completed",
                        "metadata": None,
                        "artifacts": [],
                    },
                    "metadata": None,
                },
                {
                    "id": "interaction-agent-1",
                    "thread_id": thread_id,
                    "parent_interaction_id": None,
                    "kind": "agent_run",
                    "status": "running",
                    "created_at": "2026-04-08T00:00:01Z",
                    "updated_at": "2026-04-08T00:00:02Z",
                    "last_event_at": "2026-04-08T00:00:02Z",
                    "latest_display_event_id": "event-agent-1",
                    "child_count": 1,
                    "latest_display_event": {
                        "id": "event-agent-1",
                        "interaction_id": "interaction-agent-1",
                        "event_type": "started",
                        "created_at": "2026-04-08T00:00:02Z",
                        "content": "I started a deeper investigation.",
                        "is_display_event": True,
                        "status": "running",
                        "metadata": None,
                        "artifacts": [],
                    },
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

    def list_child_interactions(self, *, parent_interaction_id: str, limit: int):
        del limit
        return {
            "items": [
                {
                    "id": "interaction-child-1",
                    "thread_id": "thread-123",
                    "parent_interaction_id": parent_interaction_id,
                    "kind": "deep_agent",
                    "status": "queued",
                    "created_at": "2026-04-08T00:00:03Z",
                    "updated_at": "2026-04-08T00:00:03Z",
                    "last_event_at": "2026-04-08T00:00:03Z",
                    "latest_display_event_id": "event-child-1",
                    "child_count": 0,
                    "latest_display_event": {
                        "id": "event-child-1",
                        "interaction_id": "interaction-child-1",
                        "event_type": "queued",
                        "created_at": "2026-04-08T00:00:03Z",
                        "content": "Queued child investigation.",
                        "is_display_event": True,
                        "status": "queued",
                        "metadata": None,
                        "artifacts": [],
                    },
                    "metadata": {"label": "Deep Agent"},
                }
            ],
            "has_more": False,
            "next_before": None,
        }

    def list_interaction_events(self, *, interaction_id: str, limit: int, before_ts=None, before_id=None):
        del interaction_id, limit, before_ts, before_id
        return {
            "items": [
                {
                    "id": "event-started-1",
                    "interaction_id": "interaction-agent-1",
                    "event_type": "started",
                    "created_at": "2026-04-08T00:00:01Z",
                    "content": "Started run.",
                    "is_display_event": True,
                    "status": "running",
                    "metadata": None,
                    "artifacts": [],
                },
                {
                    "id": "event-summary-1",
                    "interaction_id": "interaction-agent-1",
                    "event_type": "child_summary",
                    "created_at": "2026-04-08T00:00:02Z",
                    "content": "Delegated task completed.",
                    "is_display_event": True,
                    "status": "running",
                    "metadata": {"child_interaction_id": "interaction-child-1"},
                    "artifacts": [],
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
