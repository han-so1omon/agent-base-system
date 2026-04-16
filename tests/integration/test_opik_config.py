import os
from pathlib import Path
import pytest
from base_agent_system.config import Settings, load_settings

def test_config_loads_opik_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://example.com:7687")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_POSTGRES_URI", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_ENABLED", "true")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_PROJECT_NAME", "base-agent-system")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_WORKSPACE", "default")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_API_KEY_NAME", "OPIK_API_KEY")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_URL", "https://www.comet.com/opik/api")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_USE_LOCAL", "false")

    settings = load_settings()

    assert settings.opik_enabled is True
    assert settings.opik_project_name == "base-agent-system"
    assert settings.opik_workspace == "default"
    assert settings.opik_api_key_name == "OPIK_API_KEY"
    assert settings.opik_url == "https://www.comet.com/opik/api"
    assert settings.opik_use_local is False

def test_opik_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://example.com:7687")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_POSTGRES_URI", "postgresql://user:pass@localhost/db")
    # Ensure no OPIK env vars are set
    for key in list(os.environ.keys()):
        if key.startswith("BASE_AGENT_SYSTEM_OPIK_"):
            monkeypatch.delenv(key, raising=False)
            
    settings = load_settings()
    assert settings.opik_enabled is False
