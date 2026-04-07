import pytest
from fastapi.testclient import TestClient

from base_agent_system.runtime_services import _InMemoryGraphitiBackend


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv(
        "BASE_AGENT_SYSTEM_POSTGRES_URI",
        "postgresql://postgres:postgres@localhost:5432/app",
    )


def test_app_module_imports_without_required_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BASE_AGENT_SYSTEM_NEO4J_URI", raising=False)
    monkeypatch.delenv("BASE_AGENT_SYSTEM_POSTGRES_URI", raising=False)

    from base_agent_system.api import app as app_module

    assert app_module.app is not None


def test_live_returns_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)

    from base_agent_system.api.app import create_app

    with TestClient(create_app(memory_backend=_InMemoryGraphitiBackend())) as client:
        response = client.get("/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_service_unavailable_when_dependencies_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _base_env(monkeypatch)

    from base_agent_system.api.app import create_app

    app = create_app(
        initialize_dependencies=False,
        memory_backend=_InMemoryGraphitiBackend(),
    )

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_ready_returns_ok_when_dependencies_initialize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _base_env(monkeypatch)

    from base_agent_system.api.app import create_app

    with TestClient(create_app(memory_backend=_InMemoryGraphitiBackend())) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_service_unavailable_when_backend_checks_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _base_env(monkeypatch)

    from base_agent_system.api.app import create_app

    app = create_app(memory_backend=_InMemoryGraphitiBackend())

    def _fail() -> dict[str, bool]:
        return {"neo4j": True, "postgres": False}

    with TestClient(app) as client:
        client.app.state.runtime_state.readiness_checks = _fail
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_create_app_uses_distinct_runtime_state_per_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _base_env(monkeypatch)

    from base_agent_system.api.app import create_app

    first_app = create_app()
    second_app = create_app()

    assert first_app.state.runtime_state is not second_app.state.runtime_state


def test_create_app_accepts_explicit_in_memory_backend_for_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _base_env(monkeypatch)

    from base_agent_system.api.app import create_app

    backend = _InMemoryGraphitiBackend()

    app = create_app(initialize_dependencies=False, memory_backend=backend)

    with TestClient(app):
        pass

    assert backend is not None
