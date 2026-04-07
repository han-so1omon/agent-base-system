from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from base_agent_system.config import Settings
from base_agent_system.ingestion.markdown_loader import load_markdown_documents
from base_agent_system.workflow.graph import build_workflow

from .contracts import (
    ApiRouterContributor,
    CliCommandContributor,
    IngestionConnector,
    RetrievalProvider,
    WorkflowBuilder,
)


@dataclass(slots=True)
class ExtensionRegistry:
    ingestion_connectors: dict[str, IngestionConnector] = field(default_factory=dict)
    retrieval_providers: dict[str, RetrievalProvider] = field(default_factory=dict)
    workflow_builders: dict[str, WorkflowBuilder] = field(default_factory=dict)
    _api_router_contributors: list[ApiRouterContributor] = field(default_factory=list)
    _cli_command_contributors: list[CliCommandContributor] = field(default_factory=list)

    def register_ingestion_connector(self, key: str, connector: IngestionConnector) -> None:
        self._register_unique(self.ingestion_connectors, key, connector)

    def register_retrieval_provider(self, key: str, provider: RetrievalProvider) -> None:
        self._register_unique(self.retrieval_providers, key, provider)

    def register_workflow_builder(self, key: str, builder: WorkflowBuilder) -> None:
        self._register_unique(self.workflow_builders, key, builder)

    def register_api_router_contributor(self, contributor: ApiRouterContributor) -> None:
        self._api_router_contributors.append(contributor)

    def register_cli_command_contributor(self, contributor: CliCommandContributor) -> None:
        self._cli_command_contributors.append(contributor)

    def get_ingestion_connector(self, key: str) -> IngestionConnector:
        return self._get_required(self.ingestion_connectors, key)

    def get_retrieval_provider(self, key: str) -> RetrievalProvider:
        return self._get_required(self.retrieval_providers, key)

    def get_workflow_builder(self, key: str) -> WorkflowBuilder:
        return self._get_required(self.workflow_builders, key)

    def get_api_router_contributors(self) -> Sequence[ApiRouterContributor]:
        return tuple(self._api_router_contributors)

    def get_cli_command_contributors(self) -> Sequence[CliCommandContributor]:
        return tuple(self._cli_command_contributors)

    @staticmethod
    def _register_unique(registry: dict[str, Any], key: str, value: Any) -> None:
        if key in registry:
            raise ValueError(f"duplicate extension registration: {key}")
        registry[key] = value

    @staticmethod
    def _get_required(registry: dict[str, Any], key: str) -> Any:
        try:
            return registry[key]
        except KeyError as exc:
            raise KeyError(key) from exc


def create_default_registry(settings: Settings | None = None) -> ExtensionRegistry:
    del settings
    registry = ExtensionRegistry()
    registry.register_ingestion_connector("markdown", _MarkdownDirectoryConnector())
    registry.register_retrieval_provider("local", _LocalRetrievalProvider())
    registry.register_workflow_builder("default", build_workflow)
    registry.register_api_router_contributor(_BuiltinApiRouterContributor())
    registry.register_cli_command_contributor(_BuiltinCliCommandContributor())
    return registry


class _MarkdownDirectoryConnector:
    def load(self, source: Any) -> Any:
        return load_markdown_documents(Path(source))


class _LocalRetrievalProvider:
    def query(self, text: str, *, top_k: int) -> list[Any]:
        raise NotImplementedError("default retrieval provider contract is registered but not directly invoked")


class _BuiltinApiRouterContributor:
    def routers(self) -> Sequence[APIRouter]:
        from base_agent_system.api.routes_health import router as health_router
        from base_agent_system.api.routes_ingest import router as ingest_router
        from base_agent_system.api.routes_query import router as query_router

        return (health_router, ingest_router, query_router)


class _BuiltinCliCommandContributor:
    def register(
        self,
        parser: argparse.ArgumentParser,
        subparsers: argparse._SubParsersAction,
    ) -> None:
        del parser

        check_connections = subparsers.add_parser("check-connections")
        check_connections.set_defaults(
            handler=lambda args: __import__("base_agent_system.cli.main", fromlist=["run_check_connections"]).run_check_connections()
        )

        ingest = subparsers.add_parser("ingest")
        ingest.add_argument("path")
        ingest.set_defaults(
            handler=lambda args: __import__("base_agent_system.cli.main", fromlist=["run_ingest"]).run_ingest(args.path)
        )

        ask = subparsers.add_parser("ask")
        ask.add_argument("question")
        ask.set_defaults(
            handler=lambda args: __import__("base_agent_system.cli.main", fromlist=["run_ask"]).run_ask(args.question)
        )

        smoke_test = subparsers.add_parser("smoke-test")
        smoke_test.set_defaults(
            handler=lambda args: __import__("base_agent_system.cli.main", fromlist=["run_smoke_test"]).run_smoke_test()
        )
