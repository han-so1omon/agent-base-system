"""Dependency accessors for application wiring."""

from __future__ import annotations

from functools import lru_cache
import socket
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from base_agent_system.app_state import AppState
from base_agent_system.memory.graphiti_service import GraphitiMemoryBackend
from base_agent_system.config import Settings, load_settings
from base_agent_system.observability import create_observability_service
from base_agent_system.runtime_services import build_runtime_services

if TYPE_CHECKING:
    from base_agent_system.extensions.registry import ExtensionRegistry


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def create_app_state(
    settings: Settings | None = None,
    *,
    memory_backend: GraphitiMemoryBackend | None = None,
    extension_registry: ExtensionRegistry | None = None,
) -> AppState:
    runtime_settings = settings or get_settings()
    observability_service = create_observability_service(runtime_settings)
    ingest_service, workflow_service, interaction_repository = build_runtime_services(
        runtime_settings,
        memory_backend=memory_backend,
        extension_registry=extension_registry,
        observability_service=observability_service,
    )
    return AppState(
        settings=runtime_settings,
        workflow_service=workflow_service,
        ingest_service=ingest_service,
        interaction_repository=interaction_repository,
        observability_service=observability_service,
    )


def initialize_app_state(app_state: AppState) -> AppState:
    app_state.readiness_checks = lambda: dependency_status(app_state)
    return app_state


def shutdown_app_state(app_state: AppState) -> None:
    app_state.neo4j_driver = None
    app_state.postgres_pool = None
    if app_state.workflow_service is not None and hasattr(app_state.workflow_service, "close"):
        app_state.workflow_service.close()
    app_state.workflow_service = None
    app_state.ingest_service = None
    app_state.interaction_repository = None
    app_state.observability_service = None


def dependency_status(app_state: AppState) -> dict[str, bool]:
    return {
        "neo4j": _tcp_dependency_ready(app_state.settings.neo4j_uri, default_port=7687),
        "postgres": _tcp_dependency_ready(app_state.settings.postgres_uri, default_port=5432),
    }


def dependencies_ready(app_state: AppState) -> bool:
    checks = app_state.readiness_checks
    if checks is None:
        return False
    return all(checks().values())


def _tcp_dependency_ready(uri: str, *, default_port: int) -> bool:
    parsed = urlparse(uri)
    if not parsed.hostname:
        return False

    try:
        with socket.create_connection(
            (parsed.hostname, parsed.port or default_port),
            timeout=1,
        ):
            return True
    except OSError:
        return False
