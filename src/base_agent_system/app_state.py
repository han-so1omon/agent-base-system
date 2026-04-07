"""Shared process state for the application."""

from collections.abc import Callable
from dataclasses import dataclass

from base_agent_system.config import Settings


@dataclass(slots=True)
class AppState:
    settings: Settings
    neo4j_driver: object | None = None
    postgres_pool: object | None = None
    workflow_service: object | None = None
    ingest_service: object | None = None
    readiness_checks: Callable[[], dict[str, bool]] | None = None
