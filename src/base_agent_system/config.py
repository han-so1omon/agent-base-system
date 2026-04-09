"""Typed runtime configuration for the application."""

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    neo4j_uri: str = ""
    postgres_uri: str = ""
    app_env: str = "development"
    llm_model: str = "gpt-4o-mini"
    openai_model: str = "gpt-4.1-mini"
    openai_api_key_name: str = "OPENAI_API_KEY"
    anthropic_model: str = "claude-3-7-sonnet"
    anthropic_api_key_name: str = "ANTHROPIC_API_KEY"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j"
    neo4j_database: str = "neo4j"
    docs_seed_path: Path = Path("docs/seed")
    chunk_size: int = 1000
    chunk_overlap: int = 200
    graphiti_telemetry_enabled: bool = False
    api_port: int = 8000
    debug_interactions_enabled: bool = False
    interactions_page_size: int = 20

    def __post_init__(self) -> None:
        missing_fields = []
        if not self.neo4j_uri.strip():
            missing_fields.append("neo4j_uri")
        if not self.postgres_uri.strip():
            missing_fields.append("postgres_uri")
        if missing_fields:
            raise ValueError(
                "Missing required configuration: " + ", ".join(missing_fields)
            )


def load_settings() -> Settings:
    return Settings(
        app_env=_get_env("BASE_AGENT_SYSTEM_APP_ENV", "development"),
        llm_model=_get_env("BASE_AGENT_SYSTEM_LLM_MODEL", "gpt-4o-mini"),
        openai_model=_get_env("BASE_AGENT_SYSTEM_OPENAI_MODEL", "gpt-4.1-mini"),
        openai_api_key_name=_get_env("BASE_AGENT_SYSTEM_OPENAI_API_KEY_NAME", "OPENAI_API_KEY"),
        anthropic_model=_get_env("BASE_AGENT_SYSTEM_ANTHROPIC_MODEL", "claude-3-7-sonnet"),
        anthropic_api_key_name=_get_env("BASE_AGENT_SYSTEM_ANTHROPIC_API_KEY_NAME", "ANTHROPIC_API_KEY"),
        neo4j_uri=_get_env("BASE_AGENT_SYSTEM_NEO4J_URI", ""),
        neo4j_user=_get_env("BASE_AGENT_SYSTEM_NEO4J_USER", "neo4j"),
        neo4j_password=_get_env("BASE_AGENT_SYSTEM_NEO4J_PASSWORD", "neo4j"),
        neo4j_database=_get_env("BASE_AGENT_SYSTEM_NEO4J_DATABASE", "neo4j"),
        postgres_uri=_get_env("BASE_AGENT_SYSTEM_POSTGRES_URI", ""),
        docs_seed_path=Path(_get_env("BASE_AGENT_SYSTEM_DOCS_SEED_PATH", "docs/seed")),
        chunk_size=int(_get_env("BASE_AGENT_SYSTEM_CHUNK_SIZE", "1000")),
        chunk_overlap=int(_get_env("BASE_AGENT_SYSTEM_CHUNK_OVERLAP", "200")),
        graphiti_telemetry_enabled=_get_bool_env("BASE_AGENT_SYSTEM_GRAPHITI_TELEMETRY_ENABLED", False),
        api_port=int(_get_env("BASE_AGENT_SYSTEM_API_PORT", "8000")),
        debug_interactions_enabled=_get_bool_env("BASE_AGENT_SYSTEM_DEBUG_INTERACTIONS_ENABLED", False),
        interactions_page_size=int(_get_env("BASE_AGENT_SYSTEM_INTERACTIONS_PAGE_SIZE", "20")),
    )


def _get_env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
