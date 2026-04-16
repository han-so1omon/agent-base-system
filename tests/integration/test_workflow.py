from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from base_agent_system.config import Settings
from base_agent_system.memory.graphiti_service import (
    GraphitiMemoryBackend,
    GraphitiMemoryService,
)
from base_agent_system.runtime_services import (
    IngestService,
    WorkflowService,
    build_runtime_services,
)


def _settings() -> Settings:
    return Settings(
        neo4j_uri="bolt://localhost:7687",
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
    )


def _base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASE_AGENT_SYSTEM_NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv(
        "BASE_AGENT_SYSTEM_POSTGRES_URI",
        "postgresql://postgres:postgres@localhost:5432/app",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")


class _StubRetrievalService:
    def __init__(self, results: list[Any]) -> None:
        self.results = results

    def set_index(self, index: Any) -> None:
        pass


class _StubMemoryService:
    def __init__(self, results: list[Any]) -> None:
        self.results = results

    def initialize_indices(self) -> None:
        pass

    def close(self) -> None:
        pass


class _StubIngestService:
    def run(self, path: str | None = None) -> dict[str, int]:
        return {"file_count": 0, "chunk_count": 0}


class _StubWorkflowService:
    def close(self) -> None:
        pass


class _InMemoryGraphitiBackend(GraphitiMemoryBackend):
    def initialize_indices(self) -> None:
        pass

    def store_episode(self, episode: Any) -> None:
        pass

    def search_memory(self, query: str, *, thread_id: str) -> list[Any]:
        return []


def test_build_runtime_services_initializes_all_expected_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _base_env(monkeypatch)
    with patch("base_agent_system.runtime_services.build_postgres_checkpointer") as mock_build_cp:
        ingest_service, workflow_service, interaction_repository = build_runtime_services(
            _settings(),
            memory_backend=_InMemoryGraphitiBackend(),
        )

    assert isinstance(ingest_service, IngestService)
    assert isinstance(workflow_service, WorkflowService)
    assert interaction_repository is not None
    workflow_service.close()


def test_build_runtime_services_accepts_custom_service_factories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_retrieval_factory(settings):
        observed["retrieval_settings"] = settings
        return _StubRetrievalService([]), _TempDir()

    def fake_memory_factory(settings, *, memory_backend=None):
        observed["memory_settings"] = settings
        observed["memory_backend"] = memory_backend
        return _StubMemoryService([])

    def fake_ingest_factory(settings, *, retrieval_service, index_dir, connector=None):
        observed["ingest_settings"] = settings
        observed["ingest_retrieval_service"] = retrieval_service
        observed["ingest_index_dir"] = index_dir
        observed["ingest_connector"] = connector
        return _StubIngestService()

    def fake_workflow_factory(
        settings,
        *,
        retrieval_service,
        memory_service,
        temp_dir,
        workflow_builder,
        interaction_repository,
        topic_preview_generator,
        observability_service,
    ):
        observed["workflow_settings"] = settings
        observed["workflow_retrieval_service"] = retrieval_service
        observed["workflow_memory_service"] = memory_service
        observed["workflow_temp_dir"] = temp_dir
        observed["workflow_builder"] = workflow_builder
        observed["interaction_repository"] = interaction_repository
        observed["topic_preview_generator"] = topic_preview_generator
        observed["workflow_observability_service"] = observability_service
        return _StubWorkflowService()

    ingest_service, workflow_service, interaction_repository = build_runtime_services(
        _settings(),
        memory_backend=_InMemoryGraphitiBackend(),
        retrieval_service_factory=fake_retrieval_factory,
        memory_service_factory=fake_memory_factory,
        ingest_service_factory=fake_ingest_factory,
        workflow_service_factory=fake_workflow_factory,
    )

    assert isinstance(ingest_service, _StubIngestService)
    assert isinstance(workflow_service, _StubWorkflowService)
    assert interaction_repository is not None

    assert observed["retrieval_settings"] == _settings()
    assert observed["memory_settings"] == _settings()
    assert observed["memory_backend"] is not None
    assert observed["ingest_settings"] == _settings()
    assert observed["ingest_retrieval_service"] is not None
    assert observed["workflow_settings"] == _settings()
    assert observed["workflow_retrieval_service"] is not None
    assert observed["workflow_memory_service"] is not None
    assert observed["workflow_temp_dir"] is not None
    assert observed["workflow_builder"] is not None
    assert observed["interaction_repository"] is not None
    assert observed["topic_preview_generator"] is not None
    assert observed["workflow_observability_service"] is not None


def test_workflow_execution_records_persisted_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _base_env(monkeypatch)
    from base_agent_system.interactions.repository import InMemoryInteractionRepository

    repo = InMemoryInteractionRepository()

    def mock_workflow_builder(**kwargs):
        class _MockApp:
            def invoke(self, payload, **kwargs):
                return {
                    "thread_id": payload["thread_id"],
                    "answer": "workflow answer",
                    "messages": [],
                    "citations": [],
                    "debug": {"tool_calls": 0},
                    "interaction": {
                        "used_tools": False,
                        "tool_call_count": 0,
                        "tools_used": [],
                        "steps": [{"type": "thought", "content": "test"}],
                    },
                }

        return _MockApp()

    settings = _settings()
    with patch("base_agent_system.runtime_services.build_postgres_checkpointer") as mock_build_cp:
        ingest_service, workflow_service, interaction_repository = build_runtime_services(
            settings,
            memory_backend=_InMemoryGraphitiBackend(),
            workflow_service_factory=lambda *args, **kwargs: WorkflowService(
                **{
                    "settings": settings,
                    **kwargs,
                    "workflow_builder": mock_workflow_builder,
                    "interaction_repository": repo,
                }
            ),
        )


    import asyncio

    interaction = repo.create_interaction(
        thread_id="t1",
        kind="agent_run",
        status="running",
    )
    # We must use the ID generated by the repo if we don't mock it
    interaction_id = interaction.id

    result = asyncio.run(
        workflow_service.arun(thread_id="t1", interaction_id=interaction_id, query="hello")
    )

    assert result["answer"] == "workflow answer"
    interactions_page = repo.list_interactions(thread_id="t1", limit=10)
    agent_interaction = next(i for i in interactions_page.items if i.kind == "agent_run")
    assert agent_interaction.id == interaction_id


    # Verify metadata fields from canonical steps refactor
    # For agent_run kind, arun sets the interaction metadata.
    metadata = agent_interaction.metadata
    assert getattr(metadata, "used_tools", None) is False
    assert getattr(metadata, "tool_call_count", None) == 0
    assert getattr(metadata, "steps", None) == [{"type": "thought", "content": "test"}]




def test_firecrawl_tools_added_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from base_agent_system.config import Settings
    from base_agent_system.workflow.graph import build_workflow

    settings = Settings(
        **{
            **_settings().__dict__,
            "firecrawl_api_url": "http://firecrawl:3002",
            "app_env": "development",
        }
    )

    # We must patch _should_use_synthetic_workflow because app_env "development" still might not be enough if it checks for neo4j_uri etc correctly
    monkeypatch.setattr(
        "base_agent_system.workflow.graph._should_use_synthetic_workflow", lambda s: False
    )

    captured_tools = []

    def fake_create_react_agent(model, tools, **kwargs):
        captured_tools.extend(tools)
        return type("MockAgent", (), {})()

    monkeypatch.setattr(
        "base_agent_system.workflow.graph.create_react_agent", fake_create_react_agent
    )
    monkeypatch.setattr("base_agent_system.workflow.graph._build_model", lambda settings: object())

    build_workflow(
        settings=settings,
        retrieval_service=_StubRetrievalService([]),
        memory_service=_StubMemoryService([]),
    )

    tool_names = [getattr(t, "name", "") for t in captured_tools]
    assert "firecrawl_scrape" in tool_names
    assert "firecrawl_search" in tool_names
    assert "firecrawl_crawl" in tool_names
    assert "firecrawl_status" in tool_names


def test_web_search_prompt_does_not_bypass_tools() -> None:
    from base_agent_system.workflow.graph import _should_bypass_tools

    assert _should_bypass_tools(
        [{"role": "user", "content": "Search firecrawl.dev for their latest documentation updates"}]
    ) is False


def test_firecrawl_tool_messages_count_as_tool_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    from base_agent_system.workflow.graph import AgentWorkflowApp
    from langchain_core.messages import AIMessage, ToolMessage

    class _MockReactApp:
        def invoke(self, payload, **kwargs):
            return {
                "messages": [
                    AIMessage(content="", tool_calls=[]),
                    ToolMessage(content="URL: https://docs.firecrawl.dev\nContent: Update", tool_call_id="call-1", name="firecrawl_search"),
                    AIMessage(content="Here is the latest Firecrawl documentation update summary."),
                ]
            }

    app = AgentWorkflowApp(
        _MockReactApp(),
        model=object(),
        tool_context={
            "docs_result_handler": lambda results: None,
            "memory_result_handler": lambda results: None,
        },
    )

    result = app.invoke(
        {
            "thread_id": "thread-1",
            "messages": [
                {"role": "user", "content": "Search firecrawl.dev for their latest documentation updates"}
            ],
        }
    )

    assert result["interaction"]["used_tools"] is True
    assert result["interaction"]["tool_call_count"] == 1
    assert result["interaction"]["tools_used"] == ["firecrawl_search"]
    assert result["debug"]["tool_calls"] == 1


class _TempDir:
    def cleanup(self) -> None:
        return None
