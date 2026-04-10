from __future__ import annotations

from datetime import UTC, datetime


def test_in_memory_schedule_repository_stores_generic_schedule_records() -> None:
    from base_agent_system.scheduling.repository import InMemoryScheduleRepository

    repository = InMemoryScheduleRepository()
    schedule = repository.create_schedule(
        thread_id="thread-template",
        prompt="Run recurring domain research",
        cadence="0 * * * *",
        next_run_at="2026-04-10T00:00:00Z",
        metadata={
            "thread_strategy": "new_thread_per_run",
            "context_policy": {"seed_thread_ids": ["thread-a"]},
        },
    )

    claimed = repository.claim_due_schedules(now="2026-04-10T00:00:00Z", limit=10)

    assert schedule.metadata["thread_strategy"] == "new_thread_per_run"
    assert [item.id for item in claimed] == [schedule.id]


def test_in_memory_schedule_repository_updates_run_timestamps_and_skips_disabled() -> None:
    from base_agent_system.scheduling.repository import InMemoryScheduleRepository

    repository = InMemoryScheduleRepository()
    disabled = repository.create_schedule(
        thread_id="thread-disabled",
        prompt="Disabled run",
        cadence="0 * * * *",
        next_run_at="2026-04-10T00:00:00Z",
        enabled=False,
    )
    active = repository.create_schedule(
        thread_id="thread-active",
        prompt="Active run",
        cadence="0 * * * *",
        next_run_at="2026-04-10T00:00:00Z",
    )

    claimed = repository.claim_due_schedules(now="2026-04-10T00:00:00Z", limit=10)
    repository.mark_schedule_ran(
        schedule_id=active.id,
        last_run_at="2026-04-10T00:00:00Z",
        next_run_at="2026-04-10T01:00:00Z",
    )

    assert [item.id for item in claimed] == [active.id]
    assert disabled.id not in {item.id for item in claimed}
    stored = repository.get_schedule(schedule_id=active.id)
    assert stored is not None
    assert stored.last_run_at == "2026-04-10T00:00:00Z"
    assert stored.next_run_at == "2026-04-10T01:00:00Z"


def test_postgres_schedule_repository_initializes_schema_and_claims_due_schedules() -> None:
    from base_agent_system.scheduling.repository import PostgresScheduleRepository

    state = _FakeScheduleDatabaseState()
    repository = PostgresScheduleRepository(
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        connection_factory=lambda: _FakeScheduleConnection(state),
    )

    repository.initialize_schema()
    schedule = repository.create_schedule(
        thread_id="thread-postgres",
        prompt="Run recurring domain research",
        cadence="0 * * * *",
        next_run_at="2026-04-10T00:00:00Z",
        metadata={"context_policy": {"seed_thread_ids": ["thread-a"]}},
    )
    claimed = repository.claim_due_schedules(now="2026-04-10T00:00:00Z", limit=10)

    assert state.schema_initialized is True
    assert claimed[0].id == schedule.id
    assert claimed[0].metadata == {"context_policy": {"seed_thread_ids": ["thread-a"]}}


class _FakeScheduleDatabaseState:
    def __init__(self) -> None:
        self.schema_initialized = False
        self.rows: list[dict[str, object]] = []


class _FakeScheduleConnection:
    def __init__(self, state: _FakeScheduleDatabaseState) -> None:
        self._state = state

    def __enter__(self) -> _FakeScheduleConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self):
        return _FakeScheduleCursor(self._state)

    def commit(self) -> None:
        return None


class _FakeScheduleCursor:
    def __init__(self, state: _FakeScheduleDatabaseState) -> None:
        self._state = state
        self._results: list[dict[str, object]] = []

    def __enter__(self) -> _FakeScheduleCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> None:
        params = params or ()
        normalized_query = " ".join(query.split()).lower()
        if normalized_query.startswith("create table if not exists schedules"):
            self._state.schema_initialized = True
            self._results = []
            return
        if normalized_query.startswith("create index"):
            self._results = []
            return
        if normalized_query.startswith("insert into schedules"):
            self._state.rows.append(
                {
                    "id": params[0],
                    "thread_id": params[1],
                    "prompt": params[2],
                    "cadence": params[3],
                    "enabled": params[4],
                    "next_run_at": params[5],
                    "last_run_at": params[6],
                    "metadata": params[7].obj,
                }
            )
            self._results = []
            return
        if normalized_query.startswith("select id, thread_id, prompt, cadence, enabled, next_run_at, last_run_at, metadata from schedules where enabled = true and next_run_at <= %s"):
            now = _parse_ts(params[0])
            limit = int(params[1])
            rows = [row for row in self._state.rows if row["enabled"] and _parse_ts(row["next_run_at"]) <= now]
            rows.sort(key=lambda item: _parse_ts(item["next_run_at"]))
            self._results = rows[:limit]
            return
        if normalized_query.startswith("update schedules set last_run_at = %s, next_run_at = %s where id = %s"):
            for row in self._state.rows:
                if row["id"] == params[2]:
                    row["last_run_at"] = params[0]
                    row["next_run_at"] = params[1]
            self._results = []
            return
        if normalized_query.startswith("select id, thread_id, prompt, cadence, enabled, next_run_at, last_run_at, metadata from schedules where id = %s"):
            self._results = [row for row in self._state.rows if row["id"] == params[0]]
            return
        raise AssertionError(f"Unexpected query: {query}")

    def fetchall(self) -> list[dict[str, object]]:
        return list(self._results)

    def fetchone(self) -> dict[str, object] | None:
        return self._results[0] if self._results else None


def _parse_ts(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)
