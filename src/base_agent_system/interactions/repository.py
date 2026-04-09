"""Interaction thread storage boundary."""

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
    InteractionPage,
    InteractionThreadSummary,
)


class InMemoryInteractionRepository:
    def __init__(self) -> None:
        self._interactions: list[Interaction] = []
        self._debug_details: dict[str, DebugInteractionDetail] = {}
        self._topic_previews: dict[str, str] = {}

    def initialize_schema(self) -> None:
        return None

    def store_user_interaction(self, *, thread_id: str, content: str, topic_preview: str | None = None) -> Interaction:
        interaction = Interaction(
            id=f"interaction-{uuid4()}",
            thread_id=thread_id,
            kind="user",
            content=content,
            created_at=_now_iso(),
        )
        if thread_id not in self._topic_previews and topic_preview:
            self._topic_previews[thread_id] = topic_preview
        self._interactions.append(interaction)
        return interaction

    def store_agent_run_interaction(
        self,
        *,
        thread_id: str,
        content: str,
        tool_call_count: int,
        tools_used: list[str],
        steps: list[dict[str, object]],
        intermediate_reasoning: dict[str, object] | None,
    ) -> Interaction:
        interaction = Interaction(
            id=f"interaction-{uuid4()}",
            thread_id=thread_id,
            kind="agent_run",
            content=content,
            created_at=_now_iso(),
            metadata=AgentRunMetadata(
                used_tools=tool_call_count > 0,
                tool_call_count=tool_call_count,
                tools_used=tools_used,
            ),
        )
        self._interactions.append(interaction)
        self._debug_details[interaction.id] = DebugInteractionDetail(
            thread_id=thread_id,
            interaction_id=interaction.id,
            steps=steps,
            reasoning=intermediate_reasoning,
        )
        return interaction

    def list_threads(self, *, limit: int) -> list[InteractionThreadSummary]:
        latest_by_thread: dict[str, Interaction] = {}
        for interaction in self._interactions:
            latest_by_thread[interaction.thread_id] = interaction
        latest = sorted(latest_by_thread.values(), key=lambda item: item.created_at, reverse=True)[:limit]
        return [
            InteractionThreadSummary(
                thread_id=interaction.thread_id,
                preview=self._topic_previews[interaction.thread_id],
            )
            for interaction in latest
            if interaction.thread_id in self._topic_previews
        ]

    def list_interactions(
        self,
        *,
        thread_id: str,
        limit: int,
        before_ts: str | None = None,
        before_id: str | None = None,
    ) -> InteractionPage:
        del before_ts, before_id
        items = [item for item in self._interactions if item.thread_id == thread_id]
        items.sort(key=lambda item: item.created_at)
        page_items = items[-limit:]
        return InteractionPage(items=page_items, has_more=len(items) > len(page_items), next_before=None)

    def get_debug_interaction(self, *, thread_id: str, interaction_id: str) -> DebugInteractionDetail | None:
        detail = self._debug_details.get(interaction_id)
        if detail is None or detail.thread_id != thread_id:
            return None
        return detail

    def has_thread(self, *, thread_id: str) -> bool:
        return any(interaction.thread_id == thread_id for interaction in self._interactions)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


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
                    create table if not exists interaction_records (
                        id text primary key,
                        thread_id text not null,
                        kind text not null,
                        content text not null,
                        created_at timestamptz not null,
                        used_tools boolean not null,
                        tool_call_count integer not null,
                        topic_preview text null,
                        tools_used jsonb not null,
                        steps jsonb not null,
                        reasoning jsonb null
                    )
                    """
                )
                cursor.execute(
                    "create index if not exists interaction_records_thread_created_idx on interaction_records (thread_id, created_at desc, id desc)"
                )
                cursor.execute("alter table interaction_records add column if not exists topic_preview text null")
            connection.commit()

    def store_user_interaction(self, *, thread_id: str, content: str, topic_preview: str | None = None) -> Interaction:
        interaction = Interaction(
            id=f"interaction-{uuid4()}",
            thread_id=thread_id,
            kind="user",
            content=content,
            created_at=_now_iso(),
        )
        self._insert_interaction(interaction=interaction, topic_preview=topic_preview, steps=[], reasoning=None)
        return interaction

    def store_agent_run_interaction(
        self,
        *,
        thread_id: str,
        content: str,
        tool_call_count: int,
        tools_used: list[str],
        steps: list[dict[str, object]],
        intermediate_reasoning: dict[str, object] | None,
    ) -> Interaction:
        interaction = Interaction(
            id=f"interaction-{uuid4()}",
            thread_id=thread_id,
            kind="agent_run",
            content=content,
            created_at=_now_iso(),
            metadata=AgentRunMetadata(
                used_tools=tool_call_count > 0,
                tool_call_count=tool_call_count,
                tools_used=tools_used,
            ),
        )
        self._insert_interaction(
            interaction=interaction,
            topic_preview=None,
            steps=steps,
            reasoning=intermediate_reasoning,
        )
        return interaction

    def list_threads(self, *, limit: int) -> list[InteractionThreadSummary]:
        query = """
            select thread_id, topic_preview, first_content
            from (
                select
                    thread_id,
                    max(topic_preview) over (partition by thread_id) as topic_preview,
                    first_value(content) over (
                        partition by thread_id
                        order by case when kind = 'user' then 0 else 1 end, created_at asc, id asc
                    ) as first_content,
                    created_at,
                    id,
                    row_number() over (
                        partition by thread_id
                        order by created_at desc, id desc
                    ) as row_num
                from interaction_records
            ) ranked_threads
            where row_num = 1
            order by created_at desc, id desc
            limit %s
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (limit,))
                rows = cursor.fetchall()
        return [
            InteractionThreadSummary(
                thread_id=row["thread_id"],
                preview=row["topic_preview"],
            )
            for row in rows
            if row["topic_preview"]
        ]

    def list_interactions(
        self,
        *,
        thread_id: str,
        limit: int,
        before_ts: str | None = None,
        before_id: str | None = None,
    ) -> InteractionPage:
        query = """
            select id, thread_id, kind, content, created_at, used_tools, tool_call_count, tools_used
            from interaction_records
            where thread_id = %s
        """
        params: list[object] = [thread_id]
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
        ordered_rows = list(reversed(visible_rows))
        items = [self._interaction_from_row(row) for row in ordered_rows]
        next_before = None
        if has_more and visible_rows:
            last_row = visible_rows[-1]
            next_before = {
                "before_ts": _serialize_timestamp(last_row["created_at"]),
                "before_id": str(last_row["id"]),
            }
        return InteractionPage(items=items, has_more=has_more, next_before=next_before)

    def get_debug_interaction(self, *, thread_id: str, interaction_id: str) -> DebugInteractionDetail | None:
        query = """
            select thread_id, id as interaction_id, steps, reasoning
            from interaction_records
            where thread_id = %s and id = %s
        """
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (thread_id, interaction_id))
                row = cursor.fetchone()
        if row is None:
            return None
        return DebugInteractionDetail(
            thread_id=str(row["thread_id"]),
            interaction_id=str(row["interaction_id"]),
            steps=_json_value(row["steps"]),
            reasoning=_json_value(row["reasoning"]),
        )

    def has_thread(self, *, thread_id: str) -> bool:
        query = "select 1 from interaction_records where thread_id = %s limit 1"
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (thread_id,))
                return cursor.fetchone() is not None

    def _insert_interaction(
        self,
        *,
        interaction: Interaction,
        topic_preview: str | None,
        steps: list[dict[str, object]],
        reasoning: dict[str, object] | None,
    ) -> None:
        query = """
            insert into interaction_records (
                id,
                thread_id,
                kind,
                content,
                created_at,
                used_tools,
                tool_call_count,
                topic_preview,
                tools_used,
                steps,
                reasoning
            ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        metadata = interaction.metadata
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        interaction.id,
                        interaction.thread_id,
                        interaction.kind,
                        interaction.content,
                        _parse_timestamp(interaction.created_at),
                        metadata.used_tools if metadata is not None else False,
                        metadata.tool_call_count if metadata is not None else 0,
                        topic_preview,
                        Jsonb(metadata.tools_used if metadata is not None else []),
                        Jsonb(steps),
                        Jsonb(reasoning) if reasoning is not None else None,
                    ),
                )
            connection.commit()

    def _interaction_from_row(self, row: dict[str, object]) -> Interaction:
        tool_call_count = int(row["tool_call_count"])
        tools_used = _json_value(row["tools_used"])
        metadata = None
        if row["kind"] == "agent_run":
            metadata = AgentRunMetadata(
                used_tools=bool(row["used_tools"]),
                tool_call_count=tool_call_count,
                tools_used=list(tools_used),
            )
        return Interaction(
            id=str(row["id"]),
            thread_id=str(row["thread_id"]),
            kind=str(row["kind"]),
            content=str(row["content"]),
            created_at=_serialize_timestamp(row["created_at"]),
            metadata=metadata,
        )

    def _default_connection_factory(self):
        return psycopg.connect(self._postgres_uri, row_factory=dict_row)

    def close(self) -> None:
        return None


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

