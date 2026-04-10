from __future__ import annotations

import json

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


def test_post_api_chat_can_stream_plain_text_with_metadata_headers(
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

        with client.stream(
            "POST",
            "/api/chat",
            headers={"accept": "text/plain"},
            json={
                "threadId": "thread-stream-123",
                "messages": [
                    {
                        "role": "user",
                        "parts": [{"type": "text", "text": "Stream a real answer"}],
                    }
                ],
            },
        ) as response:
            body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert body == "Streaming answer from the backend agent."
    assert response.headers["x-thread-id"] == "thread-stream-123"
    assert json.loads(response.headers["x-debug"]) == {
        "memory_hits": 1,
        "document_hits": 1,
        "tool_calls": 2,
    }
    assert json.loads(response.headers["x-citations"]) == [
        {
            "source": "docs/seed/example.md",
            "snippet": "This seed document explains the markdown ingestion service.",
        }
    ]
    assert json.loads(response.headers["x-interaction"])["spawn"] == {
        "mode": "deep_agent",
        "label": "Deep Agent",
        "plan": ["search broadly", "summarize findings"],
    }
class _StubWorkflowService:
    def run(self, *, thread_id: str, messages: list[dict[str, str]]) -> dict[str, object]:
        assert thread_id == "thread-stream-123"
        assert messages == [{"role": "user", "content": "Stream a real answer"}]
        return {
            "thread_id": thread_id,
            "answer": "Streaming answer from the backend agent.",
            "citations": [
                {
                    "source": "docs/seed/example.md",
                    "snippet": "This seed document explains the markdown ingestion service.",
                }
            ],
            "debug": {"memory_hits": 1, "document_hits": 1, "tool_calls": 2},
            "interaction": {
                "spawn": {
                    "mode": "deep_agent",
                    "label": "Deep Agent",
                    "plan": ["search broadly", "summarize findings"],
                }
            },
        }
