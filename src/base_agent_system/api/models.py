"""API request and response models."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class HealthStatus(BaseModel):
    status: Literal["ok", "unavailable"]


class CitationPayload(BaseModel):
    source: str
    snippet: str


class InteractMessage(BaseModel):
    role: str
    content: str


class InteractRequest(BaseModel):
    thread_id: str
    messages: Annotated[list[InteractMessage], Field(min_length=1)]


class InteractResponse(BaseModel):
    thread_id: str
    answer: str
    citations: list[CitationPayload]
    debug: dict[str, int]


class ThreadSummaryPayload(BaseModel):
    thread_id: str
    preview: str


class AgentRunMetadataPayload(BaseModel):
    used_tools: bool
    tool_call_count: int
    tools_used: list[str]


class ArtifactReferencePayload(BaseModel):
    artifact_id: str
    storage_backend: str
    storage_uri: str
    media_type: str
    logical_role: str
    checksum: str
    metadata: dict[str, object] | None = None


class InteractionEventPayload(BaseModel):
    id: str
    interaction_id: str
    event_type: str
    created_at: str
    content: str | None = None
    is_display_event: bool
    status: str | None = None
    metadata: dict[str, object] | None = None
    artifacts: list[ArtifactReferencePayload] = []


class InteractionPayload(BaseModel):
    id: str
    thread_id: str
    parent_interaction_id: str | None = None
    kind: str
    status: str
    created_at: str
    updated_at: str | None = None
    last_event_at: str | None = None
    latest_display_event_id: str | None = None
    child_count: int = 0
    latest_display_event: InteractionEventPayload | None = None
    metadata: dict[str, object] | None = None


class InteractionPagePayload(BaseModel):
    items: list[InteractionPayload]
    has_more: bool
    next_before: dict[str, str] | None


class InteractionEventPagePayload(BaseModel):
    items: list[InteractionEventPayload]
    has_more: bool
    next_before: dict[str, str] | None


class DebugInteractionPayload(BaseModel):
    thread_id: str
    interaction_id: str
    steps: list[dict[str, object]]
    reasoning: dict[str, object] | None


class IngestRequest(BaseModel):
    path: str | None = None


class IngestResponse(BaseModel):
    file_count: int
    chunk_count: int
