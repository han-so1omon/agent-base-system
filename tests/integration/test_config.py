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

def test_config_loads_firecrawl_cloud_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://example.com:7687")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_POSTGRES_URI", "postgresql://user:pass@localhost/db")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_FIRECRAWL_API_URL", "https://api.firecrawl.dev")
    monkeypatch.setenv("BASE_AGENT_SYSTEM_FIRECRAWL_API_KEY", "fc-key")
    
    settings = load_settings()
    assert settings.firecrawl_api_url == "https://api.firecrawl.dev"
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
