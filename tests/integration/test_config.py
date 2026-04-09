from pathlib import Path

import pytest

from base_agent_system.app_state import AppState
from base_agent_system.config import Settings, load_settings
from base_agent_system.dependencies import create_app_state, get_settings
from base_agent_system.runtime_services import _InMemoryGraphitiBackend


def test_load_settings_reads_typed_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_APP_ENV", "test")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_LLM_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPENAI_API_KEY_NAME", "OPENAI_API_KEY")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_ANTHROPIC_MODEL", "claude-3-7-sonnet")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_ANTHROPIC_API_KEY_NAME", "ANTHROPIC_API_KEY")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_USER", "neo4j")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_PASSWORD", "password")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_DATABASE", "neo4j")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_POSTGRES_URI", "postgresql://postgres:postgres@localhost:5432/app")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_DOCS_SEED_PATH", "docs/seed")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_CHUNK_SIZE", "512")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_CHUNK_OVERLAP", "64")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_GRAPHITI_TELEMETRY_ENABLED", "false")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_API_PORT", "9000")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_DEBUG_INTERACTIONS_ENABLED", "true")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_INTERACTIONS_PAGE_SIZE", "15")

    settings = load_settings()

    assert isinstance(settings, Settings)
    assert settings.app_env == "test"
    assert settings.llm_model == "gpt-4o-mini"
    assert settings.openai_model == "gpt-4.1-mini"
    assert settings.openai_api_key_name == "OPENAI_API_KEY"
    assert not hasattr(settings, "ai_gateway_api_key_name")
    assert not hasattr(settings, "ai_gateway_base_url")
    assert settings.anthropic_model == "claude-3-7-sonnet"
    assert settings.anthropic_api_key_name == "ANTHROPIC_API_KEY"
    assert settings.neo4j_uri == "bolt://localhost:7687"
    assert settings.neo4j_user == "neo4j"
    assert settings.neo4j_password == "password"
    assert settings.neo4j_database == "neo4j"
    assert settings.postgres_uri == "postgresql://postgres:postgres@localhost:5432/app"
    assert settings.docs_seed_path == Path("docs/seed")
    assert settings.chunk_size == 512
    assert settings.chunk_overlap == 64
    assert settings.graphiti_telemetry_enabled is False
    assert settings.api_port == 9000
    assert settings.debug_interactions_enabled is True
    assert settings.interactions_page_size == 15


def test_settings_require_neo4j_and_postgres_urls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BASE_AGENT_SYSTEM_NEO4J_URI", raising=False)
    monkeypatch.delenv("BASE_AGENT_SYSTEM_POSTGRES_URI", raising=False)

    with pytest.raises(ValueError) as exc_info:
        Settings(
            neo4j_user="neo4j",
            neo4j_password="password",
            neo4j_database="neo4j",
        )

    message = str(exc_info.value)
    assert "neo4j_uri" in message
    assert "postgres_uri" in message


def test_load_settings_rejects_whitespace_only_required_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "   ")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_USER", "neo4j")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_PASSWORD", "password")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_DATABASE", "neo4j")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_POSTGRES_URI", "\t")

    with pytest.raises(ValueError) as exc_info:
        load_settings()

    message = str(exc_info.value)
    assert "neo4j_uri" in message
    assert "postgres_uri" in message


def test_create_app_state_uses_cached_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_USER", "neo4j")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_PASSWORD", "password")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_DATABASE", "neo4j")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_POSTGRES_URI", "postgresql://postgres:postgres@localhost:5432/app")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    get_settings.cache_clear()
    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    settings = get_settings()
    state = create_app_state(settings, memory_backend=_InMemoryGraphitiBackend())

    assert isinstance(state, AppState)
    assert state.settings is settings
    assert state.neo4j_driver is None
    assert state.postgres_pool is None
    assert state.workflow_service is not None
    assert state.ingest_service is not None
