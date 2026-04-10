"""Schedule execution service."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4


class ScheduleExecutionService:
    def __init__(self, *, schedule_repository, interaction_repository, enqueue_run) -> None:
        self._schedule_repository = schedule_repository
        self._interaction_repository = interaction_repository
        self._enqueue_run = enqueue_run

    def run_due_schedules(self, *, now: str, limit: int) -> None:
        for schedule in self._schedule_repository.claim_due_schedules(now=now, limit=limit):
            thread_id = f"thread-{uuid4()}"
            interaction = self._interaction_repository.create_interaction(
                thread_id=thread_id,
                kind="agent_run",
                status="queued",
                metadata=schedule.metadata,
            )
            self._interaction_repository.append_event(
                interaction_id=interaction.id,
                event_type="message_authored",
                content=schedule.prompt,
                is_display_event=True,
                status="queued",
            )
            self._enqueue_run(
                {
                    "thread_id": thread_id,
                    "interaction_id": interaction.id,
                    "parent_interaction_id": None,
                }
            )
            self._schedule_repository.mark_schedule_ran(
                schedule_id=schedule.id,
                last_run_at=now,
                next_run_at=_next_hour(now),
            )


def _next_hour(now: str) -> str:
    timestamp = datetime.fromisoformat(now.replace("Z", "+00:00")) + timedelta(hours=1)
    return timestamp.isoformat().replace("+00:00", "Z")
