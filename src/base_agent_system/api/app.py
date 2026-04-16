"""FastAPI application wiring."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import FastAPI

from base_agent_system.dependencies import (
    create_app_state,
    initialize_app_state,
    shutdown_app_state,
)
from base_agent_system.extensions.registry import create_default_registry
from base_agent_system.memory.graphiti_service import GraphitiMemoryBackend

if TYPE_CHECKING:
    from base_agent_system.extensions.registry import ExtensionRegistry


@dataclass(slots=True)
class RuntimeStatePlaceholder:
    observability_service: object | None = None
    workflow_service: object | None = None
    interaction_repository: object | None = None


def create_app(
    *,
    initialize_dependencies: bool = True,
    memory_backend: GraphitiMemoryBackend | None = None,
    extension_registry: "ExtensionRegistry | None" = None,
) -> FastAPI:
    app = FastAPI()
    app.state.runtime_state = RuntimeStatePlaceholder()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.runtime_state = create_app_state(
            memory_backend=memory_backend,
            extension_registry=extension_registry,
        )
        if initialize_dependencies:
            initialize_app_state(app.state.runtime_state)
        try:
            yield
        finally:
            shutdown_app_state(app.state.runtime_state)

    app.router.lifespan_context = lifespan
    registry = extension_registry or create_default_registry()
    for contributor in registry.get_api_router_contributors():
        for router in contributor.routers():
            app.include_router(router)
    return app




app = create_app()
