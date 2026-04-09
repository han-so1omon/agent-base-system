"""Interaction thread read-model types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentRunMetadata:
    used_tools: bool
    tool_call_count: int
    tools_used: list[str]


@dataclass(frozen=True)
class Interaction:
    id: str
    thread_id: str
    kind: str
    content: str
    created_at: str
    metadata: AgentRunMetadata | None = None


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
class DebugInteractionDetail:
    thread_id: str
    interaction_id: str
    steps: list[dict[str, object]]
    reasoning: dict[str, object] | None
