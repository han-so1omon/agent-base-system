from __future__ import annotations

from unittest.mock import patch, MagicMock
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


def test_post_api_chat_returns_ui_message_wrapped_backend_answer(
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
            "/api/chat",
            json={
                "threadId": "thread-ui-123",
                "messages": [
                    {
                        "role": "user",
                        "parts": [{"type": "text", "text": "First question"}],
                    },
                    {
                        "role": "assistant",
                        "parts": [{"type": "text", "text": "First answer"}],
                    },
                    {
                        "role": "user",
                        "parts": [{"type": "text", "text": "Follow-up"}],
                    },
                ],
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "id": "thread-ui-123",
        "messages": [
            {
                "id": "assistant-message",
                "role": "assistant",
                "parts": [{"type": "text", "text": "The seed doc explains markdown ingestion."}],
                "metadata": {
                    "thread_id": "thread-ui-123",
                    "citations": [
                        {
                            "source": "docs/seed/example.md",
                            "snippet": "This seed document explains the markdown ingestion service.",
                        }
                    ],
                    "debug": {"memory_hits": 1, "document_hits": 1},
                },
            }
        ],
    }


def test_post_api_chat_includes_sub_interaction_metadata_when_spawned(
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

    app = create_app(initialize_dependencies=False, memory_backend=_InMemoryGraphitiBackend())

    with TestClient(app) as client:
        client.app.state.runtime_state.workflow_service = _SpawnWorkflowService()
        response = client.post(
            "/api/chat",
            json={
                "threadId": "thread-ui-spawn",
                "messages": [{"role": "user", "parts": [{"type": "text", "text": "Do deep research"}]}],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["messages"][0]["metadata"]["spawn"] == {
        "mode": "deep_agent",
        "label": "Deep Agent",
        "plan": ["search broadly", "summarize findings"],
    }


def test_post_api_chat_returns_error_for_new_thread_when_topic_preview_generation_fails(
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

    with TestClient(app, raise_server_exceptions=False) as client:
        client.app.state.runtime_state.workflow_service = _FailingPreviewWorkflowService()

        response = client.post(
            "/api/chat",
            json={
                "threadId": "thread-ui-fail",
                "messages": [
                    {
                        "role": "user",
                        "parts": [{"type": "text", "text": "Teach me about Taiwan"}],
                    }
                ],
            },
        )

    assert response.status_code == 500
    assert "topic preview" in response.text.lower()


def test_chat_api_is_traced_with_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)
    from fastapi import FastAPI
    from base_agent_system.app_state import AppState
    from base_agent_system.api.app import RuntimeStatePlaceholder
    from base_agent_system.config import Settings

    settings = Settings(
        neo4j_uri="bolt://localhost:7687",
        postgres_uri="postgresql://localhost:5432/db",
        app_env="development",
        opik_enabled=True,
        opik_url="http://localhost:8080",
    )

    app = FastAPI()
    app.state.runtime_state = RuntimeStatePlaceholder()

    mock_obs = MagicMock()
    mock_obs.start_span.return_value.__enter__.return_value = MagicMock()

    mock_workflow = MagicMock()
    mock_workflow.run.return_value = {
        "thread_id": "t1",
        "answer": "ans",
        "citations": [],
        "debug": {},
        "interaction": {},
    }

    app.state.runtime_state = AppState(
        settings=settings,
        workflow_service=mock_workflow,
        ingest_service=MagicMock(),
        interaction_repository=MagicMock(),
        observability_service=mock_obs,
    )

    from base_agent_system.api.routes_chat import router as chat_router

    app.include_router(chat_router)

    with TestClient(app) as client:
        client.post(
            "/api/chat",
            json={"threadId": "t1", "messages": [{"role": "user", "content": "hi"}]},
        )

    assert mock_obs.start_span.called
    args, kwargs = mock_obs.start_span.call_args
    assert kwargs["name"] == "POST /api/chat"
    assert kwargs["metadata"]["thread_id"] == "t1"


class _StubWorkflowService:
    def run(self, *, thread_id: str, messages: list[dict[str, str]]) -> dict[str, object]:
        assert thread_id == "thread-ui-123"
        assert messages == [
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Follow-up"},
        ]
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


class _FailingPreviewWorkflowService:
    def run(self, *, thread_id: str, messages: list[dict[str, str]]) -> dict[str, object]:
        assert thread_id == "thread-ui-fail"
        assert messages == [{"role": "user", "content": "Teach me about Taiwan"}]
        raise ValueError("topic preview generation failed")


class _SpawnWorkflowService:
    def run(self, *, thread_id: str, messages: list[dict[str, str]]) -> dict[str, object]:
        return {
            "thread_id": thread_id,
            "answer": "I started a deeper investigation.",
            "citations": [],
            "debug": {"memory_hits": 0, "document_hits": 0},
            "interaction": {
                "spawn": {
                    "mode": "deep_agent",
                    "label": "Deep Agent",
                    "plan": ["search broadly", "summarize findings"],
                }
            },
        }
