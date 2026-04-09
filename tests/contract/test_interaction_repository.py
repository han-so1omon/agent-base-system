from __future__ import annotations

from datetime import UTC, datetime

from psycopg.types.json import Jsonb

from base_agent_system.interactions.repository import InMemoryInteractionRepository


def test_interaction_repository_stores_threads_and_lists_recent_visible_interactions() -> None:
    repository = InMemoryInteractionRepository()

    repository.store_user_interaction(
        thread_id="thread-123",
        content="What does the seed doc say?",
        topic_preview="Seed doc summary",
    )
    repository.store_agent_run_interaction(
        thread_id="thread-123",
        content="The seed doc explains markdown ingestion.",
        tool_call_count=2,
        tools_used=["search_docs", "search_memory"],
        steps=[{"type": "tool_call", "tool": "search_docs"}],
        intermediate_reasoning={"kind": "chain_of_thought", "content": "internal"},
    )

    threads = repository.list_threads(limit=50)
    page = repository.list_interactions(thread_id="thread-123", limit=20)
    debug = repository.get_debug_interaction(thread_id="thread-123", interaction_id=page.items[-1].id)

    assert len(threads) == 1
    assert threads[0].thread_id == "thread-123"
    assert threads[0].preview == "Seed doc summary"
    assert [item.kind for item in page.items] == ["user", "agent_run"]
    assert page.items[-1].metadata.used_tools is True
    assert page.items[-1].metadata.tool_call_count == 2
    assert page.items[-1].metadata.tools_used == ["search_docs", "search_memory"]
    assert debug is not None
    assert debug.reasoning == {"kind": "chain_of_thought", "content": "internal"}


def test_postgres_interaction_repository_stores_threads_and_lists_recent_visible_interactions() -> None:
    from base_agent_system.interactions.repository import PostgresInteractionRepository

    state = _FakeDatabaseState()
    repository = PostgresInteractionRepository(
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        connection_factory=lambda: _FakeConnection(state),
    )

    repository.initialize_schema()
    repository.store_user_interaction(
        thread_id="thread-123",
        content="What does the seed doc say?",
        topic_preview="Seed doc summary",
    )
    repository.store_agent_run_interaction(
        thread_id="thread-123",
        content="The seed doc explains markdown ingestion.",
        tool_call_count=2,
        tools_used=["search_docs", "search_memory"],
        steps=[{"type": "tool_call", "tool": "search_docs"}],
        intermediate_reasoning={"kind": "chain_of_thought", "content": "internal"},
    )
    repository.store_user_interaction(thread_id="thread-999", content="Other thread prompt", topic_preview="Other thread summary")

    threads = repository.list_threads(limit=50)
    page = repository.list_interactions(thread_id="thread-123", limit=20)
    debug = repository.get_debug_interaction(thread_id="thread-123", interaction_id=page.items[-1].id)

    assert state.schema_initialized is True
    assert threads[0].thread_id == "thread-999"
    assert threads[0].preview == "Other thread summary"
    assert threads[1].thread_id == "thread-123"
    assert threads[1].preview == "Seed doc summary"
    assert [item.kind for item in page.items] == ["user", "agent_run"]
    assert page.items[-1].metadata.used_tools is True
    assert page.items[-1].metadata.tool_call_count == 2
    assert page.items[-1].metadata.tools_used == ["search_docs", "search_memory"]
    assert debug is not None
    assert debug.reasoning == {"kind": "chain_of_thought", "content": "internal"}


def test_postgres_interaction_repository_supports_cursor_pagination() -> None:
    from base_agent_system.interactions.repository import PostgresInteractionRepository

    state = _FakeDatabaseState()
    repository = PostgresInteractionRepository(
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        connection_factory=lambda: _FakeConnection(state),
    )

    repository.initialize_schema()
    for index in range(3):
        repository.store_user_interaction(
            thread_id="thread-cursor",
            content=f"Prompt {index}",
        )

    first_page = repository.list_interactions(thread_id="thread-cursor", limit=2)
    second_page = repository.list_interactions(
        thread_id="thread-cursor",
        limit=2,
        before_ts=first_page.next_before["before_ts"],
        before_id=first_page.next_before["before_id"],
    )

    assert [item.content for item in first_page.items] == ["Prompt 1", "Prompt 2"]
    assert first_page.has_more is True
    assert first_page.next_before is not None
    assert [item.content for item in second_page.items] == ["Prompt 0"]
    assert second_page.has_more is False


def test_interaction_repository_does_not_list_threads_without_stored_topic_preview() -> None:
    repository = InMemoryInteractionRepository()

    repository.store_user_interaction(
        thread_id="thread-fallback",
        content="What does the seed doc say about indexing and retrieval?",
    )
    repository.store_agent_run_interaction(
        thread_id="thread-fallback",
        content="The seed doc explains markdown ingestion.",
        tool_call_count=0,
        tools_used=[],
        steps=[],
        intermediate_reasoning=None,
    )

    threads = repository.list_threads(limit=10)

    assert threads == []


def test_postgres_interaction_repository_wraps_json_columns_with_jsonb() -> None:
    from base_agent_system.interactions.repository import PostgresInteractionRepository

    state = _FakeDatabaseState()
    repository = PostgresInteractionRepository(
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        connection_factory=lambda: _FakeConnection(state),
    )

    repository.initialize_schema()
    repository.store_agent_run_interaction(
        thread_id="thread-jsonb",
        content="The seed doc explains markdown ingestion.",
        tool_call_count=1,
        tools_used=["search_docs"],
        steps=[{"type": "tool_call", "tool": "search_docs"}],
        intermediate_reasoning={"kind": "chain_of_thought", "content": "internal"},
    )

    assert state.last_insert_params is not None

    assert isinstance(state.last_insert_params[8], Jsonb)
    assert state.last_insert_params[8].obj == ["search_docs"]
    assert isinstance(state.last_insert_params[9], Jsonb)
    assert state.last_insert_params[9].obj == [{"type": "tool_call", "tool": "search_docs"}]
    assert isinstance(state.last_insert_params[10], Jsonb)
    assert state.last_insert_params[10].obj == {"kind": "chain_of_thought", "content": "internal"}


class _FakeDatabaseState:
    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []
        self.schema_initialized = False
        self.last_insert_params: tuple[object, ...] | None = None


class _FakeConnection:
    def __init__(self, state: _FakeDatabaseState) -> None:
        self._state = state

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self):
        return _FakeCursor(self._state)

    def commit(self) -> None:
        return None


class _FakeCursor:
    def __init__(self, state: _FakeDatabaseState) -> None:
        self._state = state
        self._results: list[dict[str, object]] = []

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> None:
        params = params or ()
        normalized_query = " ".join(query.split()).lower()
        if normalized_query.startswith("create table") or normalized_query.startswith("create index") or normalized_query.startswith("alter table"):
            self._state.schema_initialized = True
            self._results = []
            return
        if normalized_query.startswith("insert into interaction_records"):
            self._state.last_insert_params = params
            row = {
                "id": params[0],
                "thread_id": params[1],
                "kind": params[2],
                "content": params[3],
                "created_at": params[4],
                "used_tools": params[5],
                "tool_call_count": params[6],
                "topic_preview": params[7],
                "tools_used": _unwrap_jsonb(params[8]),
                "steps": _unwrap_jsonb(params[9]),
                "reasoning": _unwrap_jsonb(params[10]),
            }
            self._state.rows.append(row)
            self._results = []
            return
        if normalized_query.startswith("select thread_id, topic_preview, first_content"):
            limit = int(params[0])
            latest_by_thread: dict[str, dict[str, object]] = {}
            for row in self._state.rows:
                existing = latest_by_thread.get(str(row["thread_id"]))
                if existing is None or _sort_key(row) > _sort_key(existing):
                    latest_by_thread[str(row["thread_id"])] = row
            latest_rows = sorted(latest_by_thread.values(), key=_sort_key, reverse=True)[:limit]
            self._results = [
                {
                    "thread_id": row["thread_id"],
                    "topic_preview": _topic_preview_for_thread(self._state.rows, str(row["thread_id"])),
                    "first_content": _first_content_for_thread(self._state.rows, str(row["thread_id"])),
                }
                for row in latest_rows
            ]
            return
        if normalized_query.startswith("select 1 from interaction_records where thread_id = %s limit 1"):
            thread_id = str(params[0])
            self._results = [{"exists": 1}] if any(row["thread_id"] == thread_id for row in self._state.rows) else []
            return
        if normalized_query.startswith("select id, thread_id, kind, content, created_at"):
            thread_id = str(params[0])
            if len(params) == 2:
                before_ts = None
                before_id = None
                limit = int(params[1])
            else:
                before_ts = params[1]
                before_id = params[2]
                limit = int(params[3])
            rows = [row for row in self._state.rows if row["thread_id"] == thread_id]
            rows.sort(key=_sort_key, reverse=True)
            if before_ts is not None and before_id is not None:
                rows = [row for row in rows if _sort_key(row) < (_parse_ts(before_ts), str(before_id))]
            self._results = rows[:limit]
            return
        if normalized_query.startswith("select thread_id, id as interaction_id, steps, reasoning"):
            thread_id = str(params[0])
            interaction_id = str(params[1])
            self._results = [
                {
                    "thread_id": row["thread_id"],
                    "interaction_id": row["id"],
                    "steps": row["steps"],
                    "reasoning": row["reasoning"],
                }
                for row in self._state.rows
                if row["thread_id"] == thread_id and row["id"] == interaction_id
            ]
            return
        raise AssertionError(f"Unexpected query: {query}")

    def fetchall(self) -> list[dict[str, object]]:
        return list(self._results)

    def fetchone(self) -> dict[str, object] | None:
        return self._results[0] if self._results else None


def _sort_key(row: dict[str, object]) -> tuple[datetime, str]:
    return _parse_ts(row["created_at"]), str(row["id"])


def _parse_ts(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _unwrap_jsonb(value: object) -> object:
    if isinstance(value, Jsonb):
        return value.obj
    return value


def _topic_preview_for_thread(rows: list[dict[str, object]], thread_id: str) -> object:
    for row in rows:
        if row["thread_id"] == thread_id and row.get("topic_preview"):
            return row["topic_preview"]
    return None


def _first_content_for_thread(rows: list[dict[str, object]], thread_id: str) -> str:
    matching_rows = [row for row in rows if row["thread_id"] == thread_id]
    matching_rows.sort(key=_sort_key)
    for row in matching_rows:
        if row["kind"] == "user":
            return str(row["content"])
    return str(matching_rows[0]["content"]) if matching_rows else ""
