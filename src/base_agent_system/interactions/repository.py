"""Interaction tree storage boundary."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from base_agent_system.interactions.models import (
    AgentRunMetadata,
    DebugInteractionDetail,
    Interaction,
    InteractionArtifactReference,
    InteractionEvent,
    InteractionEventPage,
    InteractionPage,
    InteractionThreadSummary,
)


class InMemoryInteractionRepository:
    def __init__(self) -> None:
        self._interactions: dict[str, Interaction] = {}
        self._events: list[InteractionEvent] = []

    def initialize_schema(self) -> None:
        return None

    def create_interaction(
        self,
        *,
        thread_id: str,
        kind: str,
        parent_interaction_id: str | None = None,
        status: str = "created",
        metadata: dict[str, object] | AgentRunMetadata | None = None,
    ) -> Interaction:
        created_at = _now_iso()
        if kind == "agent_run":
            if metadata and isinstance(metadata, dict):
                effective_metadata = AgentRunMetadata(
                    used_tools=metadata.get("used_tools", False),
                    tool_call_count=metadata.get("tool_call_count", 0),
                    tools_used=metadata.get("tools_used", []),
                    steps=metadata.get("steps", []),
                    spawn=metadata.get("spawn"),
                )
            elif metadata:
                effective_metadata = metadata
            else:
                effective_metadata = AgentRunMetadata(
                    used_tools=False, tool_call_count=0, tools_used=[], steps=[]
                )
        else:
            effective_metadata = metadata or {}

        interaction = Interaction(
            id=f"interaction-{uuid4()}",
            thread_id=thread_id,
            parent_interaction_id=parent_interaction_id,
            kind=kind,
            status=status,
            created_at=created_at,
            updated_at=created_at,
            last_event_at=None,
            latest_display_event_id=None,
            child_count=0,
            metadata=effective_metadata,
        )
        self._interactions[interaction.id] = interaction
        if parent_interaction_id and parent_interaction_id in self._interactions:
            parent = self._interactions[parent_interaction_id]
            self._interactions[parent_interaction_id] = Interaction(
                **{**parent.__dict__, "child_count": parent.child_count + 1}
            )
        return interaction


    def append_event(
        self,
        *,
        interaction_id: str,
        event_type: str,
        content: str | None = None,
        is_display_event: bool = False,
        status: str | None = None,
        artifacts: list[InteractionArtifactReference] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> InteractionEvent:
        created_at = _now_iso()
        event = InteractionEvent(
            id=f"event-{uuid4()}",
            interaction_id=interaction_id,
            event_type=event_type,
            created_at=created_at,
            content=content,
            is_display_event=is_display_event,
            status=status,
            artifacts=artifacts,
            metadata=metadata,
        )
        self._events.append(event)
        interaction = self._interactions[interaction_id]
        self._interactions[interaction_id] = Interaction(
            **{
                **interaction.__dict__,
                "status": status or interaction.status,
                "updated_at": created_at,
                "last_event_at": created_at,
                "latest_display_event_id": event.id if is_display_event else interaction.latest_display_event_id,
            }
        )
        return event

    def request_cancellation(self, *, interaction_id: str) -> InteractionEvent:
        return self.append_event(
            interaction_id=interaction_id,
            event_type="cancel_requested",
            content="Cancellation requested.",
            status="cancelling",
        )

    def update_interaction_metadata(
        self, *, interaction_id: str, metadata: dict[str, object] | AgentRunMetadata
    ) -> None:
        interaction = self._interactions[interaction_id]
        if interaction.kind == "agent_run" and isinstance(metadata, dict):
            metadata = AgentRunMetadata(
                used_tools=metadata.get("used_tools", False),
                tool_call_count=metadata.get("tool_call_count", 0),
                tools_used=metadata.get("tools_used", []),
                steps=metadata.get("steps", []),
                spawn=metadata.get("spawn"),
            )
        self._interactions[interaction_id] = Interaction(
            **{**interaction.__dict__, "metadata": metadata}
        )

    def list_threads(self, *, limit: int) -> list[InteractionThreadSummary]:
        roots = [item for item in self._interactions.values() if item.parent_interaction_id is None]
        roots.sort(key=lambda item: item.last_event_at or item.created_at, reverse=True)
        seen: set[str] = set()
        summaries: list[InteractionThreadSummary] = []
        for root in roots:
            if root.thread_id in seen:
                continue
            preview = _topic_preview(root.metadata)
            if preview:
                summaries.append(InteractionThreadSummary(thread_id=root.thread_id, preview=preview))
                seen.add(root.thread_id)
            if len(summaries) >= limit:
                break
        return summaries

    def list_thread_interactions(
        self,
        *,
        thread_id: str,
        limit: int,
        before_ts: str | None = None,
        before_id: str | None = None,
    ) -> InteractionPage:
        roots = [item for item in self._interactions.values() if item.thread_id == thread_id and item.parent_interaction_id is None]
        roots.sort(key=lambda item: (item.last_event_at or item.created_at, item.id), reverse=True)
        if before_ts is not None and before_id is not None:
            roots = [item for item in roots if (item.last_event_at or item.created_at, item.id) < (before_ts, before_id)]
        visible = roots[: limit + 1]
        has_more = len(visible) > limit
        items = [self._hydrate_interaction(item) for item in reversed(visible[:limit])]
        next_before = None
        if has_more and visible[:limit]:
            cursor_item = visible[limit - 1]
            next_before = {
                "before_ts": cursor_item.last_event_at or cursor_item.created_at,
                "before_id": cursor_item.id,
            }
        return InteractionPage(items=items, has_more=has_more, next_before=next_before)

    def list_interactions(
        self,
        *,
        thread_id: str,
        limit: int,
        before_ts: str | None = None,
        before_id: str | None = None,
    ) -> InteractionPage:
        return self.list_thread_interactions(
            thread_id=thread_id,
            limit=limit,
            before_ts=before_ts,
            before_id=before_id,
        )

    def list_child_interactions(
        self,
        *,
        parent_interaction_id: str,
        limit: int,
    ) -> InteractionPage:
        children = [item for item in self._interactions.values() if item.parent_interaction_id == parent_interaction_id]
        children.sort(key=lambda item: item.last_event_at or item.created_at)
        items = [self._hydrate_interaction(item) for item in children[-limit:]]
        return InteractionPage(items=items, has_more=len(children) > len(items), next_before=None)

    def list_interaction_events(
        self,
        *,
        interaction_id: str,
        limit: int,
        before_ts: str | None = None,
        before_id: str | None = None,
    ) -> InteractionEventPage:
        events = [item for item in self._events if item.interaction_id == interaction_id]
        events.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        if before_ts is not None and before_id is not None:
            events = [item for item in events if (item.created_at, item.id) < (before_ts, before_id)]
        visible = list(reversed(events[: limit + 1]))
        has_more = len(visible) > limit
        items = visible[1:] if has_more else visible
        next_before = None
        if has_more and visible:
            next_before = {"before_ts": visible[1].created_at, "before_id": visible[1].id}
        return InteractionEventPage(items=items, has_more=has_more, next_before=next_before)

    def get_interaction(self, *, interaction_id: str) -> Interaction | None:
        interaction = self._interactions.get(interaction_id)
        return None if interaction is None else self._hydrate_interaction(interaction)

    def get_debug_interaction(self, *, thread_id: str, interaction_id: str) -> DebugInteractionDetail | None:
        interaction = self._interactions.get(interaction_id)
        if interaction is None or interaction.thread_id != thread_id:
            return None
        event = self._latest_event(interaction_id, event_type="tool_summary")
        return DebugInteractionDetail(
            thread_id=thread_id,
            interaction_id=interaction_id,
            steps=list((event.metadata or {}).get("steps", [])) if event else [],
        )

    def has_thread(self, *, thread_id: str) -> bool:
        return any(item.thread_id == thread_id for item in self._interactions.values())

    def store_user_interaction(self, *, thread_id: str, content: str, topic_preview: str | None = None) -> Interaction:
        interaction = self.create_interaction(
            thread_id=thread_id,
            kind="user",
            status="completed",
            metadata={"topic_preview": topic_preview} if topic_preview else None,
        )
        self.append_event(
            interaction_id=interaction.id,
            event_type="message_authored",
            content=content,
            is_display_event=True,
            status="completed",
        )
        return self.get_interaction(interaction_id=interaction.id)

    def store_agent_run_interaction(
        self,
        *,
        thread_id: str,
        content: str,
        tool_call_count: int,
        tools_used: list[str],
        steps: list[dict[str, object]],
    ) -> Interaction:
        interaction = self.create_interaction(
            thread_id=thread_id,
            kind="agent_run",
            status="completed",
            metadata=AgentRunMetadata(
                used_tools=tool_call_count > 0,
                tool_call_count=tool_call_count,
                tools_used=tools_used,
            ),
        )
        self.append_event(
            interaction_id=interaction.id,
            event_type="message_authored",
            content=content,
            is_display_event=True,
            status="completed",
        )
        self.append_event(
            interaction_id=interaction.id,
            event_type="tool_summary",
            status="completed",
            metadata={"steps": steps},
        )
        return self.get_interaction(interaction_id=interaction.id)

    def _hydrate_interaction(self, interaction: Interaction) -> Interaction:
        latest_display_event = None
        if interaction.latest_display_event_id is not None:
            latest_display_event = next(
                (item for item in self._events if item.id == interaction.latest_display_event_id),
                None,
            )
        return Interaction(
            **{
                **interaction.__dict__,
                "metadata": _coerce_interaction_metadata(interaction.kind, interaction.metadata),
                "latest_display_event": latest_display_event,
            }
        )

    def _latest_event(self, interaction_id: str, *, event_type: str) -> InteractionEvent | None:
        for event in reversed(self._events):
            if event.interaction_id == interaction_id and event.event_type == event_type:
                return event
        return None


class PostgresInteractionRepository:
    def __init__(
        self,
        *,
        postgres_uri: str,
        connection_factory=None,
    ) -> None:
        self._postgres_uri = postgres_uri
        self._connection_factory = connection_factory or self._default_connection_factory

    def initialize_schema(self) -> None:
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    create table if not exists interactions (
                        id text primary key,
                        thread_id text not null,
                        parent_interaction_id text null,
                        kind text not null,
                        status text not null,
                        created_at timestamptz not null,
                        updated_at timestamptz not null,
                        last_event_at timestamptz null,
                        metadata jsonb not null,
                        latest_display_event_id text null,
                        child_count integer not null
                    )
                    """
                )
                cursor.execute(
                    """
                    create table if not exists interaction_events (
                        id text primary key,
                        interaction_id text not null,
                        event_type text not null,
                        created_at timestamptz not null,
                        content text null,
                        is_display_event boolean not null,
                        status text null,
                        metadata jsonb not null
                    )
                    """
                )
                cursor.execute(
                    "create index if not exists interactions_thread_root_idx on interactions (thread_id, parent_interaction_id, last_event_at desc, id desc)"
                )
                cursor.execute(
                    "create index if not exists interactions_parent_idx on interactions (parent_interaction_id, last_event_at desc, id desc)"
                )
                cursor.execute(
                    "create index if not exists interaction_events_timeline_idx on interaction_events (interaction_id, created_at desc, id desc)"
                )
                cursor.execute(
                    "alter table interaction_events add column if not exists artifacts jsonb not null default '[]'::jsonb"
                )
            connection.commit()

    def create_interaction(
        self,
        *,
        thread_id: str,
        kind: str,
        parent_interaction_id: str | None = None,
        status: str = "created",
        metadata: dict[str, object] | AgentRunMetadata | None = None,
    ) -> Interaction:
        created_at = _now_iso()
        interaction = Interaction(
            id=f"interaction-{uuid4()}",
            thread_id=thread_id,
            parent_interaction_id=parent_interaction_id,
            kind=kind,
            status=status,
            created_at=created_at,
            updated_at=created_at,
            last_event_at=None,
            latest_display_event_id=None,
            child_count=0,
            metadata=metadata,
        )
        query = """
            insert into interactions (
                id, thread_id, parent_interaction_id, kind, status,
                created_at, updated_at, last_event_at, metadata,
                latest_display_event_id, child_count
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        interaction.id,
                        interaction.thread_id,
                        interaction.parent_interaction_id,
                        interaction.kind,
                        interaction.status,
                        _parse_timestamp(interaction.created_at),
                        _parse_timestamp(interaction.updated_at or interaction.created_at),
                        None,
                        Jsonb(_metadata_value(metadata)),
                        None,
                        0,
                    ),
                )
            connection.commit()
        return interaction

    def append_event(
        self,
        *,
        interaction_id: str,
        event_type: str,
        content: str | None = None,
        is_display_event: bool = False,
        status: str | None = None,
        artifacts: list[InteractionArtifactReference] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> InteractionEvent:
        created_at = _now_iso()
        event = InteractionEvent(
            id=f"event-{uuid4()}",
            interaction_id=interaction_id,
            event_type=event_type,
            created_at=created_at,
            content=content,
            is_display_event=is_display_event,
            status=status,
            artifacts=artifacts,
            metadata=metadata,
        )
        insert_query = """
            insert into interaction_events (
                id, interaction_id, event_type, created_at,
                content, is_display_event, status, metadata, artifacts
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        update_query = """
            update interactions set
                status = %s,
                updated_at = %s,
                last_event_at = %s,
                latest_display_event_id = %s
            where id = %s
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    insert_query,
                    (
                        event.id,
                        event.interaction_id,
                        event.event_type,
                        _parse_timestamp(event.created_at),
                        event.content,
                        event.is_display_event,
                        event.status,
                        Jsonb(event.metadata or {}),
                        Jsonb([artifact.__dict__ for artifact in artifacts or []]),
                    ),
                )
                cursor.execute(
                    update_query,
                    (
                        status or "created",
                        _parse_timestamp(event.created_at),
                        _parse_timestamp(event.created_at),
                        event.id if is_display_event else self.get_interaction(interaction_id=interaction_id).latest_display_event_id,
                        interaction_id,
                    ),
                )
            connection.commit()
        return event

    def request_cancellation(self, *, interaction_id: str) -> InteractionEvent:
        return self.append_event(
            interaction_id=interaction_id,
            event_type="cancel_requested",
            content="Cancellation requested.",
            status="cancelling",
        )

    def list_threads(self, *, limit: int) -> list[InteractionThreadSummary]:
        query = """
            select id, thread_id, parent_interaction_id, kind, status,
                   created_at, updated_at, last_event_at, metadata,
                   latest_display_event_id, child_count
            from interactions
            where parent_interaction_id is null
            order by coalesce(last_event_at, created_at) desc, id desc
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()
        summaries: list[InteractionThreadSummary] = []
        for row in rows:
            preview = _topic_preview(_json_value(row["metadata"]))
            if not preview:
                continue
            summaries.append(InteractionThreadSummary(thread_id=row["thread_id"], preview=preview))
            if len(summaries) >= limit:
                break
        return summaries

    def list_thread_interactions(
        self,
        *,
        thread_id: str,
        limit: int,
        before_ts: str | None = None,
        before_id: str | None = None,
    ) -> InteractionPage:
        query = """
            select id, thread_id, parent_interaction_id, kind, status,
                   created_at, updated_at, last_event_at, metadata,
                   latest_display_event_id, child_count
            from interactions
            where thread_id = %s and parent_interaction_id is null
        """
        params: list[object] = [thread_id]
        if before_ts is not None and before_id is not None:
            query += " and (coalesce(last_event_at, created_at), id) < (%s::timestamptz, %s)"
            params.extend([before_ts, before_id])
        query += " order by coalesce(last_event_at, created_at) desc, id desc limit %s"
        params.append(limit + 1)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
        has_more = len(rows) > limit
        visible_rows = rows[:limit]
        items = [self._hydrate_interaction(row) for row in reversed(visible_rows)]
        next_before = None
        if has_more and visible_rows:
            next_before = {
                "before_ts": _serialize_timestamp(visible_rows[-1]["last_event_at"] or visible_rows[-1]["created_at"]),
                "before_id": str(visible_rows[-1]["id"]),
            }
        return InteractionPage(items=items, has_more=has_more, next_before=next_before)

    def list_interactions(
        self,
        *,
        thread_id: str,
        limit: int,
        before_ts: str | None = None,
        before_id: str | None = None,
    ) -> InteractionPage:
        return self.list_thread_interactions(
            thread_id=thread_id,
            limit=limit,
            before_ts=before_ts,
            before_id=before_id,
        )

    def list_child_interactions(self, *, parent_interaction_id: str, limit: int) -> InteractionPage:
        query = """
            select id, thread_id, parent_interaction_id, kind, status,
                   created_at, updated_at, last_event_at, metadata,
                   latest_display_event_id, child_count
            from interactions
            where parent_interaction_id = %s
            order by coalesce(last_event_at, created_at) desc, id desc
            limit %s
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (parent_interaction_id, limit + 1))
                rows = cursor.fetchall()
        has_more = len(rows) > limit
        visible_rows = rows[:limit]
        items = [self._hydrate_interaction(row) for row in reversed(visible_rows)]
        return InteractionPage(items=items, has_more=has_more, next_before=None)

    def list_interaction_events(
        self,
        *,
        interaction_id: str,
        limit: int,
        before_ts: str | None = None,
        before_id: str | None = None,
    ) -> InteractionEventPage:
        query = """
            select id, interaction_id, event_type, created_at, content,
                   is_display_event, status, metadata, artifacts
            from interaction_events
            where interaction_id = %s
        """
        params: list[object] = [interaction_id]
        if before_ts is not None and before_id is not None:
            query += " and (created_at, id) < (%s::timestamptz, %s)"
            params.extend([before_ts, before_id])
        query += " order by created_at desc, id desc limit %s"
        params.append(limit + 1)
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
        has_more = len(rows) > limit
        visible_rows = rows[:limit]
        ordered = list(reversed(visible_rows))
        next_before = None
        if has_more and visible_rows:
            next_before = {
                "before_ts": _serialize_timestamp(visible_rows[-1]["created_at"]),
                "before_id": str(visible_rows[-1]["id"]),
            }
        return InteractionEventPage(
            items=[self._event_from_row(row) for row in ordered],
            has_more=has_more,
            next_before=next_before,
        )

    def get_interaction(self, *, interaction_id: str) -> Interaction | None:
        query = """
            select id, thread_id, parent_interaction_id, kind, status,
                   created_at, updated_at, last_event_at, metadata,
                   latest_display_event_id, child_count
            from interactions
            where id = %s
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (interaction_id,))
                row = cursor.fetchone()
        return None if row is None else self._hydrate_interaction(row)

    def get_debug_interaction(self, *, thread_id: str, interaction_id: str) -> DebugInteractionDetail | None:
        interaction = self.get_interaction(interaction_id=interaction_id)
        if interaction is None or interaction.thread_id != thread_id:
            return None
        events = self.list_interaction_events(interaction_id=interaction_id, limit=100)
        tool_summary = next((item for item in events.items if item.event_type == "tool_summary"), None)
        return DebugInteractionDetail(
            thread_id=thread_id,
            interaction_id=interaction_id,
            steps=list((tool_summary.metadata or {}).get("steps", [])) if tool_summary else [],
        )

    def has_thread(self, *, thread_id: str) -> bool:
        query = "select 1 from interactions where thread_id = %s limit 1"
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (thread_id,))
                return cursor.fetchone() is not None

    def store_user_interaction(self, *, thread_id: str, content: str, topic_preview: str | None = None) -> Interaction:
        interaction = self.create_interaction(
            thread_id=thread_id,
            kind="user",
            status="completed",
            metadata={"topic_preview": topic_preview} if topic_preview else None,
        )
        self.append_event(
            interaction_id=interaction.id,
            event_type="message_authored",
            content=content,
            is_display_event=True,
            status="completed",
        )
        return self.get_interaction(interaction_id=interaction.id)

    def store_agent_run_interaction(
        self,
        *,
        thread_id: str,
        content: str,
        tool_call_count: int,
        tools_used: list[str],
        steps: list[dict[str, object]],
    ) -> Interaction:
        interaction = self.create_interaction(
            thread_id=thread_id,
            kind="agent_run",
            status="completed",
            metadata=AgentRunMetadata(
                used_tools=tool_call_count > 0,
                tool_call_count=tool_call_count,
                tools_used=tools_used,
            ),
        )
        self.append_event(
            interaction_id=interaction.id,
            event_type="message_authored",
            content=content,
            is_display_event=True,
            status="completed",
        )
        self.append_event(
            interaction_id=interaction.id,
            event_type="tool_summary",
            status="completed",
            metadata={"steps": steps},
        )
        return self.get_interaction(interaction_id=interaction.id)

    def _hydrate_interaction(self, row: dict[str, object]) -> Interaction:
        interaction = Interaction(
            id=str(row["id"]),
            thread_id=str(row["thread_id"]),
            parent_interaction_id=None if row["parent_interaction_id"] is None else str(row["parent_interaction_id"]),
            kind=str(row["kind"]),
            status=str(row["status"]),
            created_at=_serialize_timestamp(row["created_at"]),
            updated_at=_serialize_timestamp(row["updated_at"]),
            last_event_at=None if row["last_event_at"] is None else _serialize_timestamp(row["last_event_at"]),
            metadata=_coerce_interaction_metadata(str(row["kind"]), _json_value(row["metadata"])),
            latest_display_event_id=None if row["latest_display_event_id"] is None else str(row["latest_display_event_id"]),
            child_count=int(row["child_count"]),
        )
        latest_display_event = None
        if interaction.latest_display_event_id is not None:
            event_query = """
                select id, interaction_id, event_type, created_at, content,
                       is_display_event, status, metadata, artifacts
                from interaction_events
                where interaction_id = %s
                order by created_at desc, id desc
                limit 100
            """
            with self._connection_factory() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(event_query, (interaction.id,))
                    rows = cursor.fetchall()
            for row in rows:
                event = self._event_from_row(row)
                if event.id == interaction.latest_display_event_id:
                    latest_display_event = event
                    break
        return Interaction(**{**interaction.__dict__, "latest_display_event": latest_display_event})

    def _event_from_row(self, row: dict[str, object]) -> InteractionEvent:
        return InteractionEvent(
            id=str(row["id"]),
            interaction_id=str(row["interaction_id"]),
            event_type=str(row["event_type"]),
            created_at=_serialize_timestamp(row["created_at"]),
            content=None if row["content"] is None else str(row["content"]),
            is_display_event=bool(row["is_display_event"]),
            status=None if row["status"] is None else str(row["status"]),
            artifacts=_coerce_event_artifacts(_json_value(row.get("artifacts"))),
            metadata=_json_value(row["metadata"]),
        )

    def _default_connection_factory(self):
        return psycopg.connect(self._postgres_uri, row_factory=dict_row)

    def close(self) -> None:
        return None


def _metadata_value(metadata: dict[str, object] | AgentRunMetadata | None) -> dict[str, object]:
    if metadata is None:
        return {}
    if isinstance(metadata, AgentRunMetadata):
        return {
            "used_tools": metadata.used_tools,
            "tool_call_count": metadata.tool_call_count,
            "tools_used": metadata.tools_used,
            "steps": metadata.steps,
            "spawn": metadata.spawn,
        }
    return metadata


def _coerce_interaction_metadata(kind: str, metadata: object) -> AgentRunMetadata | dict[str, object] | None:
    if metadata is None:
        return None
    if isinstance(metadata, AgentRunMetadata):
        return metadata
    if kind == "agent_run" and isinstance(metadata, dict):
        if "topic_preview" in metadata or "context_policy" in metadata or "spawn" in metadata:
            return metadata
        return AgentRunMetadata(
            used_tools=bool(metadata.get("used_tools", False)),
            tool_call_count=int(metadata.get("tool_call_count", 0)),
            tools_used=list(metadata.get("tools_used", [])),
            steps=list(metadata.get("steps", [])),
            spawn=metadata.get("spawn"),
        )
    if isinstance(metadata, dict):
        return metadata
    return None


def _topic_preview(metadata: object) -> str | None:
    if not isinstance(metadata, dict):
        return None
    preview = metadata.get("topic_preview")
    if isinstance(preview, str) and preview:
        return preview
    return None


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _serialize_timestamp(value: object) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return str(value)


def _json_value(value: object):
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value


def _coerce_event_artifacts(value: object) -> list[InteractionArtifactReference] | None:
    if value in (None, []):
        return None
    if not isinstance(value, list):
        return None
    artifacts: list[InteractionArtifactReference] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        artifacts.append(
            InteractionArtifactReference(
                artifact_id=str(item["artifact_id"]),
                storage_backend=str(item["storage_backend"]),
                storage_uri=str(item["storage_uri"]),
                media_type=str(item["media_type"]),
                logical_role=str(item["logical_role"]),
                checksum=str(item["checksum"]),
                metadata=item.get("metadata") if isinstance(item.get("metadata"), dict) else None,
            )
        )
    return artifacts or None
