from pathlib import Path
import pytest
from base_agent_system.config import Settings, load_settings

def test_load_settings_reads_neo4j_uri_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://example.com:7687")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_POSTGRES_URI", "postgresql://user:pass@localhost/db")
    settings = load_settings()
    assert settings.neo4j_uri == "bolt://example.com:7687"

def test_settings_validates_required_fields() -> None:
    with pytest.raises(ValueError, match="neo4j_uri"):
        Settings(postgres_uri="postgresql://user:pass@localhost/db")
    with pytest.raises(ValueError, match="postgres_uri"):
        Settings(neo4j_uri="bolt://localhost:7687")

def test_config_loads_firecrawl_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://example.com:7687")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_POSTGRES_URI", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_FIRECRAWL_API_URL", "http://firecrawl:3002")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_FIRECRAWL_API_KEY", "fc-key")
    
    settings = load_settings()
    assert settings.firecrawl_api_url == "http://firecrawl:3002"
    assert settings.firecrawl_api_key == "fc-key"


def test_config_loads_arq_and_artifact_storage_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://example.com:7687")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_POSTGRES_URI", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_ARQ_REDIS_URI", "redis://localhost:6379/0")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_ARQ_QUEUE_NAME", "deep-agent")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_ARTIFACT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_ARTIFACT_STORAGE_DIR", "/tmp/base-agent-artifacts")

    settings = load_settings()

    assert settings.arq_redis_uri == "redis://localhost:6379/0"
    assert settings.arq_queue_name == "deep-agent"
    assert settings.artifact_storage_backend == "local"
    assert settings.artifact_storage_dir == Path("/tmp/base-agent-artifacts")


def test_config_loads_opik_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://example.com:7687")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_POSTGRES_URI", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_ENABLED", "true")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_PROJECT_NAME", "agent-system-prod")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_WORKSPACE", "team-workspace")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_API_KEY_NAME", "CUSTOM_OPIK_KEY")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_URL", "https://opik.example.com")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_OPIK_USE_LOCAL", "true")

    settings = load_settings()

    assert settings.opik_enabled is True
    assert settings.opik_project_name == "agent-system-prod"
    assert settings.opik_workspace == "team-workspace"
    assert settings.opik_api_key_name == "CUSTOM_OPIK_KEY"
    assert settings.opik_url == "https://opik.example.com"
    assert settings.opik_use_local is True
