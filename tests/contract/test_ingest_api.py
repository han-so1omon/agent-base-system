from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from base_agent_system.runtime_services import _InMemoryGraphitiBackend


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv(
        "BASE_AGENT_SYSTEM_POSTGRES_URI",
        "postgresql://postgres:postgres@localhost:5432/app",
    )


def test_post_ingest_returns_file_and_chunk_counts_for_explicit_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
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

    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    app = create_app(
        initialize_dependencies=False,
        memory_backend=_InMemoryGraphitiBackend(),
    )

    with TestClient(app) as client:
        client.app.state.runtime_state.ingest_service = _StubIngestService(
            expected_path=str(docs_dir),
            response={"file_count": 2, "chunk_count": 5},
        )

        response = client.post("/ingest", json={"path": str(docs_dir)})

    assert response.status_code == 200
    assert response.json() == {"file_count": 2, "chunk_count": 5}


def test_post_ingest_defaults_to_docs_seed_when_path_not_provided(
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
        client.app.state.runtime_state.ingest_service = _StubIngestService(
            expected_path="docs/seed",
            response={"file_count": 2, "chunk_count": 3},
        )

        response = client.post("/ingest", json={})

    assert response.status_code == 200
    assert response.json() == {"file_count": 2, "chunk_count": 3}


class _StubIngestService:
    def __init__(self, *, expected_path: str, response: dict[str, int]) -> None:
        self._expected_path = expected_path
        self._response = response

    def run(self, *, path: str | None = None) -> dict[str, int]:
        assert path == self._expected_path
        return self._response
