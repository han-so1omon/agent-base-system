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


def test_post_interact_returns_answer_citations_thread_id_and_debug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    app = create_app(
        initialize_dependencies=False,
        memory_backend=_InMemoryGraphitiBackend(),
    )

    with TestClient(app) as client:
        client.app.state.runtime_state.workflow_service = _StubWorkflowService()

        response = client.post(
            "/interact",
            json={
                "thread_id": "thread-123",
                "messages": [{"role": "user", "content": "What does the seed doc say?"}],
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "thread_id": "thread-123",
        "answer": "The seed doc explains markdown ingestion.",
        "citations": [
            {
                "source": "docs/seed/example.md",
                "snippet": "This seed document explains the markdown ingestion service.",
            }
        ],
        "debug": {"memory_hits": 1, "document_hits": 1},
    }


def test_post_interact_rejects_empty_messages(monkeypatch: pytest.MonkeyPatch) -> None:
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

    with TestClient(
        create_app(
            initialize_dependencies=False,
            memory_backend=_InMemoryGraphitiBackend(),
        )
    ) as client:
        response = client.post(
            "/interact",
            json={"thread_id": "thread-123", "messages": []},
        )

    assert response.status_code == 422


def test_post_query_is_not_available(monkeypatch: pytest.MonkeyPatch) -> None:
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

    with TestClient(
        create_app(
            initialize_dependencies=False,
            memory_backend=_InMemoryGraphitiBackend(),
        )
    ) as client:
        response = client.post(
            "/query",
            json={"thread_id": "thread-123", "query": "What does the seed doc say?"},
        )

    assert response.status_code == 404


class _StubWorkflowService:
    def run(self, *, thread_id: str, messages: list[dict[str, str]]) -> dict[str, object]:
        assert thread_id == "thread-123"
        assert messages == [{"role": "user", "content": "What does the seed doc say?"}]
        return {
            "thread_id": thread_id,
            "answer": "The seed doc explains markdown ingestion.",
            "citations": [
                {
                    "source": "docs/seed/example.md",
                    "snippet": "This seed document explains the markdown ingestion service.",
                }
            ],
            "debug": {"memory_hits": 1, "document_hits": 1},
        }
