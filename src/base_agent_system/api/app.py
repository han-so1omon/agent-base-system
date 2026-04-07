"""FastAPI application wiring."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from base_agent_system.dependencies import (
    create_app_state,
    initialize_app_state,
    shutdown_app_state,
)
from base_agent_system.memory.graphiti_service import GraphitiMemoryBackend

from .routes_health import router as health_router
from .routes_ingest import router as ingest_router
from .routes_query import router as query_router


def create_app(
    *,
    initialize_dependencies: bool = True,
    memory_backend: GraphitiMemoryBackend | None = None,
) -> FastAPI:
    runtime_state = object()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.runtime_state = create_app_state(memory_backend=memory_backend)
        if initialize_dependencies:
            initialize_app_state(app.state.runtime_state)
        try:
            yield
        finally:
            shutdown_app_state(app.state.runtime_state)

    app = FastAPI(lifespan=lifespan)
    app.state.runtime_state = runtime_state
    app.include_router(health_router)
    app.include_router(ingest_router)
    app.include_router(query_router)
    return app


app = create_app()
