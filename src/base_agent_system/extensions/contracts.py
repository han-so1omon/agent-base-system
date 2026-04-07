from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from fastapi import APIRouter

from base_agent_system.config import Settings


class IngestionConnector(Protocol):
    def load(self, source: Any) -> Any:
        ...


class RetrievalProvider(Protocol):
    def query(self, text: str, *, top_k: int) -> Any:
        ...


class WorkflowBuilder(Protocol):
    def __call__(
        self,
        *,
        settings: Settings,
        retrieval_service: Any,
        memory_service: Any,
        checkpointer: object | None = None,
        state_graph_factory: Callable[[type[Any]], Any] | None = None,
    ) -> Any:
        ...


class ApiRouterContributor(Protocol):
    def routers(self) -> Sequence[APIRouter]:
        ...


class CliCommandContributor(Protocol):
    def register(
        self,
        parser: argparse.ArgumentParser,
        subparsers: argparse._SubParsersAction,
    ) -> None:
        ...
