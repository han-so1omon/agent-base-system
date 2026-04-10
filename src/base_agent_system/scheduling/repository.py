"""Schedule repository implementations."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from base_agent_system.scheduling.models import Schedule


class InMemoryScheduleRepository:
    def __init__(self) -> None:
        self._schedules: dict[str, Schedule] = {}

    def initialize_schema(self) -> None:
        return None

    def create_schedule(
        self,
        *,
        thread_id: str,
        prompt: str,
        cadence: str,
        next_run_at: str,
        enabled: bool = True,
        metadata: dict[str, object] | None = None,
    ) -> Schedule:
        schedule = Schedule(
            id=f"schedule-{uuid4()}",
            thread_id=thread_id,
            prompt=prompt,
            cadence=cadence,
            enabled=enabled,
            next_run_at=next_run_at,
            last_run_at=None,
            metadata=metadata,
        )
        self._schedules[schedule.id] = schedule
        return schedule

    def claim_due_schedules(self, *, now: str, limit: int) -> list[Schedule]:
        due = [
            item
            for item in self._schedules.values()
            if item.enabled and _parse_timestamp(item.next_run_at) <= _parse_timestamp(now)
        ]
        due.sort(key=lambda item: _parse_timestamp(item.next_run_at))
        return due[:limit]

    def mark_schedule_ran(self, *, schedule_id: str, last_run_at: str, next_run_at: str) -> None:
        schedule = self._schedules[schedule_id]
        self._schedules[schedule_id] = Schedule(
            **{**schedule.__dict__, "last_run_at": last_run_at, "next_run_at": next_run_at}
        )

    def get_schedule(self, *, schedule_id: str) -> Schedule | None:
        return self._schedules.get(schedule_id)


class PostgresScheduleRepository:
    def __init__(self, *, postgres_uri: str, connection_factory=None) -> None:
        self._postgres_uri = postgres_uri
        self._connection_factory = connection_factory or self._default_connection_factory

    def initialize_schema(self) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    create table if not exists schedules (
                        id text primary key,
                        thread_id text not null,
                        prompt text not null,
                        cadence text not null,
                        enabled boolean not null,
                        next_run_at timestamptz not null,
                        last_run_at timestamptz null,
                        metadata jsonb not null
                    )
                    """
                )
                cursor.execute(
                    "create index if not exists schedules_due_idx on schedules (enabled, next_run_at asc, id asc)"
                )
            connection.commit()

    def create_schedule(
        self,
        *,
        thread_id: str,
        prompt: str,
        cadence: str,
        next_run_at: str,
        enabled: bool = True,
        metadata: dict[str, object] | None = None,
    ) -> Schedule:
        schedule = Schedule(
            id=f"schedule-{uuid4()}",
            thread_id=thread_id,
            prompt=prompt,
            cadence=cadence,
            enabled=enabled,
            next_run_at=next_run_at,
            last_run_at=None,
            metadata=metadata,
        )
        query = """
            insert into schedules (
                id, thread_id, prompt, cadence, enabled, next_run_at, last_run_at, metadata
            ) values (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        schedule.id,
                        schedule.thread_id,
                        schedule.prompt,
                        schedule.cadence,
                        schedule.enabled,
                        _parse_timestamp(schedule.next_run_at),
                        None,
                        Jsonb(schedule.metadata or {}),
                    ),
                )
            connection.commit()
        return schedule

    def claim_due_schedules(self, *, now: str, limit: int) -> list[Schedule]:
        query = """
            select id, thread_id, prompt, cadence, enabled, next_run_at, last_run_at, metadata
            from schedules
            where enabled = true and next_run_at <= %s
            order by next_run_at asc, id asc
            limit %s
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (_parse_timestamp(now), limit))
                rows = cursor.fetchall()
        return [_schedule_from_row(row) for row in rows]

    def mark_schedule_ran(self, *, schedule_id: str, last_run_at: str, next_run_at: str) -> None:
        query = "update schedules set last_run_at = %s, next_run_at = %s where id = %s"
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (_parse_timestamp(last_run_at), _parse_timestamp(next_run_at), schedule_id))
            connection.commit()

    def get_schedule(self, *, schedule_id: str) -> Schedule | None:
        query = """
            select id, thread_id, prompt, cadence, enabled, next_run_at, last_run_at, metadata
            from schedules
            where id = %s
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (schedule_id,))
                row = cursor.fetchone()
        return None if row is None else _schedule_from_row(row)

    def _default_connection_factory(self):
        return psycopg.connect(self._postgres_uri, row_factory=dict_row)


def _schedule_from_row(row: dict[str, object]) -> Schedule:
    return Schedule(
        id=str(row["id"]),
        thread_id=str(row["thread_id"]),
        prompt=str(row["prompt"]),
        cadence=str(row["cadence"]),
        enabled=bool(row["enabled"]),
        next_run_at=_serialize_timestamp(row["next_run_at"]),
        last_run_at=None if row["last_run_at"] is None else _serialize_timestamp(row["last_run_at"]),
        metadata=row["metadata"],
    )


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _serialize_timestamp(value: object) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return str(value)
