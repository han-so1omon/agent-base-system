from __future__ import annotations

from types import SimpleNamespace

import pytest

from base_agent_system.config import Settings
from base_agent_system.interactions.repository import InMemoryInteractionRepository
from base_agent_system.memory.graphiti_service import GraphitiMemoryService
from base_agent_system.memory.models import MemoryEpisode
from base_agent_system.runtime_services import _InMemoryGraphitiBackend


def _settings() -> Settings:
    return Settings(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        neo4j_database="neo4j",
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        app_env="test",
    )


@pytest.mark.asyncio
async def test_workflow_service_arun_persists_interaction_events(monkeypatch: pytest.MonkeyPatch) -> None:
    from base_agent_system.runtime_services import WorkflowService

    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    backend = _InMemoryGraphitiBackend()
    memory_service = GraphitiMemoryService(settings=_settings(), backend=backend, provider_api_key="test-key")
    memory_service.initialize_indices()
    interaction_repository = InMemoryInteractionRepository()

    workflow_service = WorkflowService(
        settings=_settings(),
        retrieval_service=SimpleNamespace(),
        memory_service=memory_service,
        temp_dir=SimpleNamespace(cleanup=lambda: None),
        interaction_repository=interaction_repository,
        workflow_builder=lambda **kwargs: _AsyncWorkflowStub(),
    )

    result = await workflow_service.arun(
        thread_id="thread-async-1",
        messages=[{"role": "user", "content": "Remember Kubernetes as my preferred deployment target."}],
    )

    assert result["answer"] == "I will remember Kubernetes."
    page = interaction_repository.list_thread_interactions(thread_id="thread-async-1", limit=20)
    assert [item.kind for item in page.items] == ["user", "agent_run"]
    assert page.items[-1].latest_display_event is not None
    assert page.items[-1].latest_display_event.content == "I will remember Kubernetes."


class _AsyncWorkflowStub:
    async def ainvoke(self, payload: dict[str, object], **kwargs) -> dict[str, object]:
        del payload, kwargs
        return {
            "thread_id": "thread-async-1",
            "answer": "I will remember Kubernetes.",
            "citations": [],
            "debug": {"document_hits": 0, "memory_hits": 0},
            "interaction": {
                "used_tools": True,
                "tool_call_count": 1,
                "tools_used": ["search_memory"],
                "steps": [{"type": "tool_call", "tool": "search_memory"}],
                "intermediate_reasoning": {"kind": "chain_of_thought", "content": "internal"},
            },
        }
