from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from base_agent_system.runtime_services import _InMemoryGraphitiBackend


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv(
        "BASE_AGENT_SYSTEM_POSTGRES_URI",
        "postgresql://postgres:postgres@localhost:5432/app",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")


def test_post_interaction_cancel_requests_cooperative_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    from base_agent_system.api.app import create_app
    from base_agent_system.interactions.repository import InMemoryInteractionRepository

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    repository = InMemoryInteractionRepository()
    interaction = repository.create_interaction(thread_id="thread-123", kind="deep_agent", status="running")

    app = create_app(initialize_dependencies=False, memory_backend=_InMemoryGraphitiBackend())
    with TestClient(app) as client:
        client.app.state.runtime_state.interaction_repository = repository
        response = client.post(f"/interactions/{interaction.id}/cancel")

    assert response.status_code == 200
    payload = response.json()
    assert payload["interaction_id"] == interaction.id
    assert payload["event_type"] == "cancel_requested"
    events = repository.list_interaction_events(interaction_id=interaction.id, limit=20)
    assert events.items[-1].event_type == "cancel_requested"
