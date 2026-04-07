import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from base_agent_system.extensions.registry import create_default_registry
from base_agent_system.runtime_services import _InMemoryGraphitiBackend


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv(
        "BASE_AGENT_SYSTEM_POSTGRES_URI",
        "postgresql://postgres:postgres@localhost:5432/app",
    )


def test_create_app_includes_routes_from_registry_contributors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _base_env(monkeypatch)

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    class _ExtraContributor:
        def routers(self) -> tuple[APIRouter, ...]:
            router = APIRouter()

            @router.get("/extra")
            def extra() -> dict[str, str]:
                return {"status": "extra"}

            return (router,)

    from base_agent_system.api.app import create_app
    from base_agent_system.config import Settings

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    registry = create_default_registry(
        Settings(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="password",
            neo4j_database="neo4j",
            postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        )
    )
    registry.register_api_router_contributor(_ExtraContributor())

    with TestClient(
        create_app(
            initialize_dependencies=False,
            memory_backend=_InMemoryGraphitiBackend(),
            extension_registry=registry,
        )
    ) as client:
        response = client.get("/extra")

    assert response.status_code == 200
    assert response.json() == {"status": "extra"}
