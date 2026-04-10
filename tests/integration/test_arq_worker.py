from __future__ import annotations

from types import SimpleNamespace

import pytest

from base_agent_system.interactions.repository import InMemoryInteractionRepository


@pytest.mark.asyncio
async def test_arq_worker_runs_child_interaction_branch_and_projects_parent_summary() -> None:
    from base_agent_system.workers.tasks import run_interaction_branch

    repository = InMemoryInteractionRepository()
    parent = repository.create_interaction(thread_id="thread-123", kind="agent_run", status="running")
    child = repository.create_interaction(
        thread_id="thread-123",
        parent_interaction_id=parent.id,
        kind="deep_agent",
        status="queued",
    )

    workflow_service = _WorkerWorkflowStub()
    context = SimpleNamespace(runtime_state=SimpleNamespace(interaction_repository=repository, workflow_service=workflow_service))

    await run_interaction_branch(
        context,
        thread_id="thread-123",
        interaction_id=child.id,
        parent_interaction_id=parent.id,
    )

    child_events = repository.list_interaction_events(interaction_id=child.id, limit=20)
    parent_events = repository.list_interaction_events(interaction_id=parent.id, limit=20)

    assert [event.event_type for event in child_events.items] == ["started", "completed"]
    assert parent_events.items[-1].event_type == "child_summary"
    assert parent_events.items[-1].metadata == {"child_interaction_id": child.id}


class _WorkerWorkflowStub:
    async def arun(self, *, thread_id: str, interaction_id: str, parent_interaction_id: str | None = None, messages=None, query=None):
        del thread_id, interaction_id, parent_interaction_id, messages, query
        return {
            "thread_id": "thread-123",
            "answer": "Delegated run completed.",
            "citations": [],
            "debug": {"document_hits": 0, "memory_hits": 0},
            "interaction": {
                "used_tools": False,
                "tool_call_count": 0,
                "tools_used": [],
                "steps": [],
                "intermediate_reasoning": None,
            },
        }


@pytest.mark.asyncio
async def test_arq_worker_records_child_branch_trace_metadata() -> None:
    from base_agent_system.workers.tasks import run_interaction_branch

    repository = InMemoryInteractionRepository()
    parent = repository.create_interaction(thread_id="thread-456", kind="agent_run", status="running")
    child = repository.create_interaction(
        thread_id="thread-456",
        parent_interaction_id=parent.id,
        kind="deep_agent",
        status="queued",
    )

    observability = _RecordingObservabilityService()
    workflow_service = _WorkerWorkflowStub()
    context = SimpleNamespace(
        runtime_state=SimpleNamespace(
            interaction_repository=repository,
            workflow_service=workflow_service,
            observability_service=observability,
        )
    )

    await run_interaction_branch(
        context,
        thread_id="thread-456",
        interaction_id=child.id,
        parent_interaction_id=parent.id,
    )

    assert observability.branch_traces == [
        {
            "name": "worker_interaction_branch",
            "metadata": {
                "thread_id": "thread-456",
                "interaction_id": child.id,
                "parent_interaction_id": parent.id,
                "branch_kind": "child",
                "status": "completed",
            },
        }
    ]


class _RecordingObservabilityService:
    def __init__(self) -> None:
        self.branch_traces: list[dict[str, object]] = []

    class _TraceContext:
        def __init__(self, owner: "_RecordingObservabilityService", name: str, metadata: dict[str, object]) -> None:
            self._owner = owner
            self._name = name
            self._metadata = metadata

        def __enter__(self) -> SimpleNamespace:
            return SimpleNamespace(name=self._name, metadata=self._metadata)

        def __exit__(self, exc_type, exc, tb) -> None:
            self._owner.branch_traces.append({"name": self._name, "metadata": dict(self._metadata)})

    def start_branch_trace(self, *, name: str, metadata: dict[str, object]) -> "_RecordingObservabilityService._TraceContext":
        return self._TraceContext(self, name, metadata)
