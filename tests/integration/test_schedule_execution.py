from __future__ import annotations

from types import SimpleNamespace


def test_schedule_service_creates_fresh_thread_and_root_interaction() -> None:
    from base_agent_system.interactions.repository import InMemoryInteractionRepository
    from base_agent_system.scheduling.repository import InMemoryScheduleRepository
    from base_agent_system.scheduling.service import ScheduleExecutionService

    schedule_repository = InMemoryScheduleRepository()
    interaction_repository = InMemoryInteractionRepository()
    enqueued: list[dict[str, object]] = []

    schedule = schedule_repository.create_schedule(
        thread_id="thread-template",
        prompt="Run recurring domain research",
        cadence="0 * * * *",
        next_run_at="2026-04-10T00:00:00Z",
        metadata={
            "context_policy": {"seed_thread_ids": ["thread-a"], "graph_expansion": "allowed"},
        },
    )

    service = ScheduleExecutionService(
        schedule_repository=schedule_repository,
        interaction_repository=interaction_repository,
        enqueue_run=lambda payload: enqueued.append(payload),
    )

    service.run_due_schedules(now="2026-04-10T00:00:00Z", limit=10)

    assert len(enqueued) == 1
    assert enqueued[0]["parent_interaction_id"] is None
    assert enqueued[0]["thread_id"] != schedule.thread_id
    page = interaction_repository.list_thread_interactions(thread_id=enqueued[0]["thread_id"], limit=20)
    assert page.items[0].kind == "agent_run"
    assert page.items[0].metadata == {"context_policy": {"seed_thread_ids": ["thread-a"], "graph_expansion": "allowed"}}
