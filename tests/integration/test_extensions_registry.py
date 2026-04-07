from __future__ import annotations

import pytest

from base_agent_system.config import Settings
from base_agent_system.extensions.registry import ExtensionRegistry, create_default_registry


def _settings() -> Settings:
    return Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        neo4j_database="neo4j",
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
    )


def test_default_registry_exposes_builtin_extension_keys() -> None:
    registry = create_default_registry(_settings())

    assert registry.get_ingestion_connector("markdown") is not None
    assert registry.get_retrieval_provider("local") is not None
    assert registry.get_workflow_builder("default") is not None
    assert registry.get_api_router_contributors()
    assert registry.get_cli_command_contributors()


def test_registry_rejects_duplicate_ingestion_connector_keys() -> None:
    registry = ExtensionRegistry()
    registry.register_ingestion_connector("markdown", object())

    with pytest.raises(ValueError, match="markdown"):
        registry.register_ingestion_connector("markdown", object())


def test_registry_raises_on_unknown_extension_keys() -> None:
    registry = ExtensionRegistry()

    with pytest.raises(KeyError, match="missing"):
        registry.get_ingestion_connector("missing")

    with pytest.raises(KeyError, match="missing"):
        registry.get_retrieval_provider("missing")

    with pytest.raises(KeyError, match="missing"):
        registry.get_workflow_builder("missing")
