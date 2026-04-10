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
