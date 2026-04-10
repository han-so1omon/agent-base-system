from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import pytest

from base_agent_system.artifacts.storage import LocalArtifactStorage
from base_agent_system.config import Settings
from base_agent_system.interactions.repository import InMemoryInteractionRepository
from base_agent_system.memory.graphiti_service import GraphitiMemoryService
from base_agent_system.runtime_services import WorkflowService, _InMemoryGraphitiBackend
from base_agent_system.workers.tasks import run_interaction_branch


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
async def test_delegated_interaction_lifecycle_projects_parent_summary_and_artifact(monkeypatch: pytest.MonkeyPatch) -> None:
    class _CheckpointerHolder:
        def open(self) -> object | None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "base_agent_system.runtime_services.build_postgres_checkpointer",
        lambda postgres_uri: _CheckpointerHolder(),
    )

    repository = InMemoryInteractionRepository()
    backend = _InMemoryGraphitiBackend()
    memory_service = GraphitiMemoryService(settings=_settings(), backend=backend, provider_api_key="test-key")
    memory_service.initialize_indices()

    with TemporaryDirectory() as tmp_dir:
        storage = LocalArtifactStorage(base_dir=Path(tmp_dir))
        parent = repository.create_interaction(thread_id="thread-123", kind="agent_run", status="running")
        repository.append_event(
            interaction_id=parent.id,
            event_type="spawned_child",
            content="Spawned deep agent.",
            is_display_event=True,
            status="running",
            metadata={"mode": "deep_agent"},
        )
        child = repository.create_interaction(
            thread_id="thread-123",
            parent_interaction_id=parent.id,
            kind="deep_agent",
            status="queued",
        )

        workflow_service = WorkflowService(
            settings=_settings(),
            retrieval_service=SimpleNamespace(),
            memory_service=memory_service,
            temp_dir=SimpleNamespace(cleanup=lambda: None),
            interaction_repository=repository,
            workflow_builder=lambda **kwargs: _LifecycleWorkflowStub(storage),
        )
        context = SimpleNamespace(runtime_state=SimpleNamespace(interaction_repository=repository, workflow_service=workflow_service))

        result = await run_interaction_branch(
            context,
            thread_id="thread-123",
            interaction_id=child.id,
            parent_interaction_id=parent.id,
        )

    assert result["answer"] == "Delegated run completed with artifact output."

    child_events = repository.list_interaction_events(interaction_id=child.id, limit=20)
    parent_events = repository.list_interaction_events(interaction_id=parent.id, limit=20)

    assert [event.event_type for event in child_events.items] == ["started", "message_authored", "tool_summary", "completed"]
    assert parent_events.items[-1].event_type == "child_summary"
    assert parent_events.items[-1].metadata == {"child_interaction_id": child.id}
    assert child_events.items[1].content == "Delegated run completed with artifact output."
    assert child_events.items[1].artifacts is not None
    assert child_events.items[1].artifacts[0].logical_role == "summary"


class _LifecycleWorkflowStub:
    def __init__(self, storage: LocalArtifactStorage) -> None:
        self._storage = storage

    async def ainvoke(self, payload: dict[str, object], **kwargs) -> dict[str, object]:
        del payload, kwargs
        artifact = self._storage.write_bytes(
            logical_role="summary",
            media_type="text/markdown",
            data=b"# Delegated summary\n",
        )
        return {
            "thread_id": "thread-123",
            "answer": "Delegated run completed with artifact output.",
            "citations": [],
            "debug": {"document_hits": 0, "memory_hits": 0},
            "interaction": {
                "used_tools": False,
                "tool_call_count": 0,
                "tools_used": [],
                "steps": [],
                "intermediate_reasoning": None,
                "artifacts": [artifact],
            },
        }
