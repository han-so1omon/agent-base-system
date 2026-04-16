from __future__ import annotations

from datetime import UTC, datetime

from psycopg.types.json import Jsonb

from base_agent_system.interactions.repository import InMemoryInteractionRepository


def test_interaction_repository_creates_interactions_and_projects_display_events() -> None:
    repository = InMemoryInteractionRepository()
    root = repository.create_interaction(
        thread_id="thread-123",
        kind="user",
        status="completed",
        metadata={"topic_preview": "Seed doc summary"},
    )
    repository.append_event(
        interaction_id=root.id,
        event_type="message_authored",
        content="What does the seed doc say?",
        is_display_event=True,
        status="completed",
    )
    child = repository.create_interaction(
        thread_id="thread-123",
        parent_interaction_id=root.id,
        kind="deep_agent",
        status="queued",
        metadata={"label": "Deep Agent"},
    )
    repository.append_event(
        interaction_id=child.id,
        event_type="queued",
        content="Starting deeper investigation.",
        is_display_event=True,
        status="queued",
    )

    threads = repository.list_threads(limit=50)
    page = repository.list_thread_interactions(thread_id="thread-123", limit=20)
    children = repository.list_child_interactions(parent_interaction_id=root.id, limit=20)

    assert len(threads) == 1
    assert threads[0].thread_id == "thread-123"
    assert threads[0].preview == "Seed doc summary"
    assert [item.kind for item in page.items] == ["user"]
    assert page.items[0].latest_display_event is not None
    assert page.items[0].latest_display_event.content == "What does the seed doc say?"
    assert len(children.items) == 1
    assert children.items[0].parent_interaction_id == root.id
    assert children.items[0].latest_display_event is not None
    assert children.items[0].latest_display_event.content == "Starting deeper investigation."


def test_interaction_repository_records_event_history_and_cancellation_states() -> None:
    repository = InMemoryInteractionRepository()
    interaction = repository.create_interaction(
        thread_id="thread-123",
        kind="deep_agent",
        status="queued",
    )
    repository.append_event(
        interaction_id=interaction.id,
        event_type="queued",
        content="Queued",
        is_display_event=True,
        status="queued",
    )
    repository.request_cancellation(interaction_id=interaction.id)
    repository.append_event(
        interaction_id=interaction.id,
        event_type="cancel_acknowledged",
        content="Stopping at next checkpoint.",
        status="cancelling",
    )
    repository.append_event(
        interaction_id=interaction.id,
        event_type="cancelled",
        content="Cancelled.",
        is_display_event=True,
        status="cancelled",
    )

    events = repository.list_interaction_events(interaction_id=interaction.id, limit=20)
    stored = repository.get_interaction(interaction_id=interaction.id)

    assert [item.event_type for item in events.items] == [
        "queued",
        "cancel_requested",
        "cancel_acknowledged",
        "cancelled",
    ]
    assert stored is not None
    assert stored.status == "cancelled"
    assert stored.latest_display_event is not None
    assert stored.latest_display_event.content == "Cancelled."


def test_interaction_repository_supports_parent_summary_projection_events() -> None:
    repository = InMemoryInteractionRepository()
    parent = repository.create_interaction(thread_id="thread-123", kind="agent_run", status="running")
    child = repository.create_interaction(
        thread_id="thread-123",
        parent_interaction_id=parent.id,
        kind="deep_agent",
        status="running",
    )
    repository.append_event(
        interaction_id=child.id,
        event_type="completed",
        content="Child completed canonical result.",
        is_display_event=True,
        status="completed",
    )
    repository.append_event(
        interaction_id=parent.id,
        event_type="child_summary",
        content="Delegated task completed with a condensed result.",
        is_display_event=True,
        status="running",
        metadata={"child_interaction_id": child.id},
    )

    page = repository.list_thread_interactions(thread_id="thread-123", limit=20)

    assert [item.id for item in page.items] == [parent.id]
    assert page.items[0].latest_display_event is not None
    assert page.items[0].latest_display_event.event_type == "child_summary"
    assert page.items[0].latest_display_event.metadata == {"child_interaction_id": child.id}


def test_in_memory_thread_listing_applies_limit_after_preview_filtering() -> None:
    repository = InMemoryInteractionRepository()
    recent = repository.create_interaction(thread_id="thread-recent", kind="agent_run", status="completed")
    repository.append_event(
        interaction_id=recent.id,
        event_type="message_authored",
        content="Recent interaction without preview",
        is_display_event=True,
        status="completed",
    )
    older = repository.create_interaction(
        thread_id="thread-older",
        kind="user",
        status="completed",
        metadata={"topic_preview": "Older preview"},
    )
    repository.append_event(
        interaction_id=older.id,
        event_type="message_authored",
        content="Older interaction with preview",
        is_display_event=True,
        status="completed",
    )

    threads = repository.list_threads(limit=1)

    assert threads == [repository.list_threads(limit=10)[0]]
    assert threads[0].thread_id == "thread-older"


def test_in_memory_child_interactions_report_has_more_when_limited() -> None:
    repository = InMemoryInteractionRepository()
    parent = repository.create_interaction(thread_id="thread-123", kind="agent_run", status="running")
    for index in range(2):
        child = repository.create_interaction(
            thread_id="thread-123",
            parent_interaction_id=parent.id,
            kind="deep_agent",
            status="queued",
        )
        repository.append_event(
            interaction_id=child.id,
            event_type="queued",
            content=f"Child {index}",
            is_display_event=True,
            status="queued",
        )

    page = repository.list_child_interactions(parent_interaction_id=parent.id, limit=1)

    assert page.has_more is True
    assert len(page.items) == 1


def test_postgres_interaction_repository_creates_schema_and_jsonb_wrapped_events() -> None:
    from base_agent_system.interactions.repository import PostgresInteractionRepository

    state = _FakeDatabaseState()
    repository = PostgresInteractionRepository(
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        connection_factory=lambda: _FakeConnection(state),
    )

    repository.initialize_schema()
    interaction = repository.create_interaction(
        thread_id="thread-jsonb",
        kind="agent_run",
        status="running",
        metadata={"topic_preview": "Seed doc summary"},
    )
    repository.append_event(
        interaction_id=interaction.id,
        event_type="tool_summary",
        content="Used two tools.",
        is_display_event=True,
        status="running",
        metadata={"tools_used": ["search_docs", "search_memory"]},
    )

    assert state.schema_statements == ["interactions", "interaction_events", "interaction_events_artifacts"]
    assert state.last_event_insert_params is not None
    assert isinstance(state.last_interaction_insert_params[8], Jsonb)
    assert state.last_interaction_insert_params[8].obj == {"topic_preview": "Seed doc summary"}
    assert isinstance(state.last_event_insert_params[7], Jsonb)
    assert state.last_event_insert_params[7].obj == {"tools_used": ["search_docs", "search_memory"]}


def test_postgres_interaction_repository_initializes_artifacts_column() -> None:
    from base_agent_system.interactions.repository import PostgresInteractionRepository

    state = _FakeDatabaseState()
    repository = PostgresInteractionRepository(
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        connection_factory=lambda: _FakeConnection(state),
    )

    repository.initialize_schema()

    assert state.schema_statements == ["interactions", "interaction_events", "interaction_events_artifacts"]


def test_postgres_interaction_repository_supports_cursor_pagination() -> None:
    from base_agent_system.interactions.repository import PostgresInteractionRepository

    state = _FakeDatabaseState()
    repository = PostgresInteractionRepository(
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        connection_factory=lambda: _FakeConnection(state),
    )

    repository.initialize_schema()
    interaction = repository.create_interaction(thread_id="thread-cursor", kind="user")
    for index in range(3):
        repository.append_event(
            interaction_id=interaction.id,
            event_type="message_authored",
            content=f"Prompt {index}",
            is_display_event=True,
            status="completed",
        )

    first_page = repository.list_interaction_events(interaction_id=interaction.id, limit=2)
    second_page = repository.list_interaction_events(
        interaction_id=interaction.id,
        limit=2,
        before_ts=first_page.next_before["before_ts"],
        before_id=first_page.next_before["before_id"],
    )

    assert [item.content for item in first_page.items] == ["Prompt 1", "Prompt 2"]
    assert first_page.has_more is True
    assert first_page.next_before is not None
    assert [item.content for item in second_page.items] == ["Prompt 0"]
    assert second_page.has_more is False


def test_postgres_interaction_repository_preserves_latest_display_event_on_non_display_updates() -> None:
    from base_agent_system.interactions.repository import PostgresInteractionRepository

    state = _FakeDatabaseState()
    repository = PostgresInteractionRepository(
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        connection_factory=lambda: _FakeConnection(state),
    )

    repository.initialize_schema()
    interaction = repository.create_interaction(thread_id="thread-display", kind="agent_run")
    display_event = repository.append_event(
        interaction_id=interaction.id,
        event_type="message_authored",
        content="Visible message",
        is_display_event=True,
        status="running",
    )
    repository.append_event(
        interaction_id=interaction.id,
        event_type="tool_summary",
        status="running",
        metadata={"steps": []},
    )

    stored = repository.get_interaction(interaction_id=interaction.id)

    assert stored is not None
    assert stored.latest_display_event_id == display_event.id
    assert stored.latest_display_event is not None
    assert stored.latest_display_event.content == "Visible message"


def test_postgres_thread_interactions_honor_before_cursor() -> None:
    from base_agent_system.interactions.repository import PostgresInteractionRepository

    state = _FakeDatabaseState()
    repository = PostgresInteractionRepository(
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        connection_factory=lambda: _FakeConnection(state),
    )

    repository.initialize_schema()
    first = repository.create_interaction(thread_id="thread-page", kind="user")
    repository.append_event(
        interaction_id=first.id,
        event_type="message_authored",
        content="First",
        is_display_event=True,
        status="completed",
    )
    second = repository.create_interaction(thread_id="thread-page", kind="user")
    repository.append_event(
        interaction_id=second.id,
        event_type="message_authored",
        content="Second",
        is_display_event=True,
        status="completed",
    )

    first_page = repository.list_thread_interactions(thread_id="thread-page", limit=1)
    second_page = repository.list_thread_interactions(
        thread_id="thread-page",
        limit=1,
        before_ts=first_page.items[0].last_event_at,
        before_id=first_page.items[0].id,
    )

    assert [item.latest_display_event.content for item in first_page.items] == ["Second"]
    assert [item.latest_display_event.content for item in second_page.items] == ["First"]


def test_postgres_interaction_repository_persists_event_artifacts() -> None:
    from base_agent_system.interactions.models import InteractionArtifactReference
    from base_agent_system.interactions.repository import PostgresInteractionRepository

    state = _FakeDatabaseState()
    repository = PostgresInteractionRepository(
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        connection_factory=lambda: _FakeConnection(state),
    )

    repository.initialize_schema()
    interaction = repository.create_interaction(thread_id="thread-artifact", kind="deep_agent")
    artifact = InteractionArtifactReference(
        artifact_id="artifact-123",
        storage_backend="local",
        storage_uri="file:///tmp/report.md",
        media_type="text/markdown",
        logical_role="summary",
        checksum="sha256:abc",
    )
    repository.append_event(
        interaction_id=interaction.id,
        event_type="message_authored",
        content="With artifact",
        is_display_event=True,
        status="completed",
        artifacts=[artifact],
    )

    events = repository.list_interaction_events(interaction_id=interaction.id, limit=20)

    assert events.items[0].artifacts == [artifact]


def test_postgres_thread_listing_applies_limit_after_preview_filtering() -> None:
    from base_agent_system.interactions.repository import PostgresInteractionRepository

    state = _FakeDatabaseState()
    repository = PostgresInteractionRepository(
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        connection_factory=lambda: _FakeConnection(state),
    )

    repository.initialize_schema()
    recent = repository.create_interaction(thread_id="thread-recent", kind="agent_run")
    repository.append_event(
        interaction_id=recent.id,
        event_type="message_authored",
        content="Recent interaction without preview",
        is_display_event=True,
        status="completed",
    )
    older = repository.create_interaction(
        thread_id="thread-older",
        kind="user",
        metadata={"topic_preview": "Older preview"},
    )
    repository.append_event(
        interaction_id=older.id,
        event_type="message_authored",
        content="Older interaction with preview",
        is_display_event=True,
        status="completed",
    )

    threads = repository.list_threads(limit=1)

    assert len(threads) == 1
    assert threads[0].thread_id == "thread-older"


def test_postgres_child_interactions_report_has_more_when_limited() -> None:
    from base_agent_system.interactions.repository import PostgresInteractionRepository

    state = _FakeDatabaseState()
    repository = PostgresInteractionRepository(
        postgres_uri="postgresql://postgres:postgres@localhost:5432/app",
        connection_factory=lambda: _FakeConnection(state),
    )

    repository.initialize_schema()
    parent = repository.create_interaction(thread_id="thread-123", kind="agent_run")
    for index in range(2):
        child = repository.create_interaction(
            thread_id="thread-123",
            parent_interaction_id=parent.id,
            kind="deep_agent",
        )
        repository.append_event(
            interaction_id=child.id,
            event_type="queued",
            content=f"Child {index}",
            is_display_event=True,
            status="queued",
        )

    page = repository.list_child_interactions(parent_interaction_id=parent.id, limit=1)

    assert page.has_more is True
    assert len(page.items) == 1


class _FakeDatabaseState:
    def __init__(self) -> None:
        self.interactions: list[dict[str, object]] = []
        self.events: list[dict[str, object]] = []
        self.schema_statements: list[str] = []
        self.last_interaction_insert_params: tuple[object, ...] | None = None
        self.last_event_insert_params: tuple[object, ...] | None = None


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
        if normalized_query.startswith("create table if not exists interactions"):
            self._state.schema_statements.append("interactions")
            self._results = []
            return
        if normalized_query.startswith("create table if not exists interaction_events"):
            self._state.schema_statements.append("interaction_events")
            self._results = []
            return
        if normalized_query.startswith("create index"):
            self._results = []
            return
        if normalized_query.startswith("alter table interaction_events add column if not exists artifacts jsonb not null default '[]'::jsonb"):
            self._state.schema_statements.append("interaction_events_artifacts")
            self._results = []
            return
        if normalized_query.startswith("insert into interactions"):
            self._state.last_interaction_insert_params = params
            self._state.interactions.append(
                {
                    "id": params[0],
                    "thread_id": params[1],
                    "parent_interaction_id": params[2],
                    "kind": params[3],
                    "status": params[4],
                    "created_at": params[5],
                    "updated_at": params[6],
                    "last_event_at": params[7],
                    "metadata": _unwrap_jsonb(params[8]),
                    "latest_display_event_id": params[9],
                    "child_count": params[10],
                }
            )
            self._results = []
            return
        if normalized_query.startswith("insert into interaction_events"):
            self._state.last_event_insert_params = params
            self._state.events.append(
                {
                    "id": params[0],
                    "interaction_id": params[1],
                    "event_type": params[2],
                    "created_at": params[3],
                    "content": params[4],
                    "is_display_event": params[5],
                    "status": params[6],
                    "metadata": _unwrap_jsonb(params[7]),
                    "artifacts": _unwrap_jsonb(params[8]),
                }
            )
            self._results = []
            return
        if normalized_query.startswith("update interactions set"):
            interaction = _interaction_by_id(self._state.interactions, str(params[-1]))
            assert interaction is not None
            interaction["status"] = params[0]
            interaction["updated_at"] = params[1]
            interaction["last_event_at"] = params[2]
            if params[3] is not None:
                interaction["latest_display_event_id"] = params[3]
            self._results = []
            return
        if normalized_query.startswith("select 1 from interactions where thread_id = %s limit 1"):
            thread_id = str(params[0])
            self._results = [{"exists": 1}] if any(row["thread_id"] == thread_id for row in self._state.interactions) else []
            return
        if normalized_query.startswith("select id, thread_id, parent_interaction_id, kind, status") and "where id = %s" not in normalized_query and "where parent_interaction_id = %s" not in normalized_query:
            if normalized_query.startswith("select id, thread_id, parent_interaction_id, kind, status, created_at, updated_at, last_event_at, metadata, latest_display_event_id, child_count from interactions where parent_interaction_id is null"):
                roots = [row for row in self._state.interactions if row["parent_interaction_id"] is None]
                roots.sort(key=_interaction_sort_key, reverse=True)
                self._results = roots
                return
            thread_id = str(params[0])
            if len(params) == 1:
                interaction = _interaction_by_id(self._state.interactions, thread_id)
                self._results = [] if interaction is None else [interaction]
                return
            if len(params) == 2:
                before_ts = None
                before_id = None
                limit = int(params[1])
            else:
                before_ts = params[1]
                before_id = params[2]
                limit = int(params[3])
            roots = [row for row in self._state.interactions if row["thread_id"] == thread_id and row["parent_interaction_id"] is None]
            roots.sort(key=_interaction_sort_key, reverse=True)
            if before_ts is not None and before_id is not None:
                roots = [row for row in roots if _interaction_sort_key(row) < (_parse_ts(before_ts), str(before_id))]
            self._results = roots[:limit]
            return
        if normalized_query.startswith("select id, interaction_id, event_type, created_at, content, is_display_event, status, metadata, artifacts from interaction_events where interaction_id = %s"):
            interaction_id = str(params[0])
            if len(params) == 1:
                before_ts = None
                before_id = None
                limit = 100
            elif len(params) == 2:
                before_ts = None
                before_id = None
                limit = int(params[1])
            else:
                before_ts = params[1]
                before_id = params[2]
                limit = int(params[3])
            events = [row for row in self._state.events if row["interaction_id"] == interaction_id]
            events.sort(key=_event_sort_key, reverse=True)
            if before_ts is not None and before_id is not None:
                events = [row for row in events if _event_sort_key(row) < (_parse_ts(before_ts), str(before_id))]
            self._results = events[:limit]
            return
        if normalized_query.startswith("select id, thread_id, parent_interaction_id, kind, status, created_at, updated_at, last_event_at, metadata, latest_display_event_id, child_count from interactions where parent_interaction_id = %s"):
            parent_id = str(params[0])
            limit = int(params[1])
            children = [row for row in self._state.interactions if row["parent_interaction_id"] == parent_id]
            children.sort(key=_interaction_sort_key, reverse=True)
            self._results = children[:limit]
            return
        if normalized_query.startswith("select id, thread_id, parent_interaction_id, kind, status, created_at, updated_at, last_event_at, metadata, latest_display_event_id, child_count from interactions where id = %s"):
            interaction = _interaction_by_id(self._state.interactions, str(params[0]))
            self._results = [] if interaction is None else [interaction]
            return
        raise AssertionError(f"Unexpected query: {query}")

    def fetchall(self) -> list[dict[str, object]]:
        return list(self._results)

    def fetchone(self) -> dict[str, object] | None:
        return self._results[0] if self._results else None


def _interaction_by_id(rows: list[dict[str, object]], interaction_id: str) -> dict[str, object] | None:
    for row in rows:
        if row["id"] == interaction_id:
            return row
    return None


def _interaction_sort_key(row: dict[str, object]) -> tuple[datetime, str]:
    return _parse_ts(row["last_event_at"] or row["created_at"]), str(row["id"])


def _event_sort_key(row: dict[str, object]) -> tuple[datetime, str]:
    return _parse_ts(row["created_at"]), str(row["id"])


def _parse_ts(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def _unwrap_jsonb(value: object) -> object:
    if isinstance(value, Jsonb):
        return value.obj
    return value
