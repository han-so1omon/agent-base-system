from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from base_agent_system.dependencies import get_settings
from base_agent_system.runtime_services import _InMemoryGraphitiBackend


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("BASE_AGENT_SYSTEM_APP_ENV", "test")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv(
        "BASE_AGENT_SYSTEM_POSTGRES_URI",
        "postgresql://postgres:postgres@localhost:5432/app",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")


def test_end_to_end_ingest_then_interact_then_follow_up_preserves_thread_memory(
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

    with TestClient(
        create_app(
            initialize_dependencies=False,
            memory_backend=_InMemoryGraphitiBackend(),
        )
    ) as client:
        ingest_response = client.post("/ingest", json={})

        assert ingest_response.status_code == 200
        assert ingest_response.json()["file_count"] >= 1
        assert ingest_response.json()["chunk_count"] >= 1

        first_query = client.post(
            "/interact",
            json={
                "thread_id": "thread-e2e",
                "messages": [{"role": "user", "content": "What does the markdown ingestion service do?"}],
            },
        )

        assert first_query.status_code == 200
        first_payload = first_query.json()
        assert first_payload["thread_id"] == "thread-e2e"
        assert "markdown ingestion service" in first_payload["answer"].lower()
        assert first_payload["citations"]
        assert first_payload["citations"][0]["source"].endswith("docs/seed/example.md")
        assert first_payload["debug"]["document_hits"] >= 1

        preference_query = client.post(
            "/interact",
            json={
                "thread_id": "thread-e2e",
                "messages": [
                    {
                        "role": "user",
                        "content": "Remember that my preferred deployment target is Kubernetes.",
                    }
                ],
            },
        )

        assert preference_query.status_code == 200

        follow_up_query = client.post(
            "/interact",
            json={
                "thread_id": "thread-e2e",
                "messages": [{"role": "user", "content": "What is my preferred deployment target?"}],
            },
        )

        assert follow_up_query.status_code == 200
        follow_up_payload = follow_up_query.json()
        assert follow_up_payload["thread_id"] == "thread-e2e"
        assert "kubernetes" in follow_up_payload["answer"].lower()
        assert follow_up_payload["debug"]["memory_hits"] >= 1
