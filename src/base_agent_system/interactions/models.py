"""Interaction tree read-model types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentRunMetadata:
    used_tools: bool
    tool_call_count: int
    tools_used: list[str]


@dataclass(frozen=True)
class InteractionArtifactReference:
    artifact_id: str
    storage_backend: str
    storage_uri: str
    media_type: str
    logical_role: str
    checksum: str
    metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class InteractionEvent:
    id: str
    interaction_id: str
    event_type: str
    created_at: str
    content: str | None = None
    is_display_event: bool = False
    status: str | None = None
    artifacts: list[InteractionArtifactReference] | None = None
    metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class Interaction:
    id: str
    thread_id: str
    kind: str
    created_at: str
    parent_interaction_id: str | None = None
    status: str = "created"
    updated_at: str | None = None
    last_event_at: str | None = None
    latest_display_event_id: str | None = None
    child_count: int = 0
    latest_display_event: InteractionEvent | None = None
    metadata: AgentRunMetadata | dict[str, object] | None = None


@dataclass(frozen=True)
class InteractionThreadSummary:
    thread_id: str
    preview: str


@dataclass(frozen=True)
class InteractionPage:
    items: list[Interaction]
    has_more: bool
    next_before: dict[str, str] | None


@dataclass(frozen=True)
class InteractionEventPage:
    items: list[InteractionEvent]
    has_more: bool
    next_before: dict[str, str] | None


@dataclass(frozen=True)
class DebugInteractionDetail:
    thread_id: str
    interaction_id: str
    steps: list[dict[str, object]]
    reasoning: dict[str, object] | None
