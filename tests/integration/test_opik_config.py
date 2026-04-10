from __future__ import annotations

import pytest

from base_agent_system.config import Settings, load_settings


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv(
        "BASE_AGENT_SYSTEM_POSTGRES_URI",
        "postgresql://postgres:postgres@localhost:5432/app",
    )


def test_opik_settings_default_to_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _base_env(monkeypatch)

    settings = load_settings()

    assert settings.opik_enabled is False
    assert settings.opik_project_name == "base-agent-system"
    assert settings.opik_workspace == ""
    assert settings.opik_api_key_name == "OPIK_API_KEY"
    assert settings.opik_url == ""
    assert settings.opik_use_local is False


def test_settings_support_optional_opik_fields_when_disabled() -> None:
    settings = Settings(
        neo4j_uri="bolt://localhost:7687",
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
    )

    assert settings.opik_enabled is False
    assert settings.opik_url == ""
    assert settings.opik_workspace == ""
