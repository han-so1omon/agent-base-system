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
