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


class InteractionPayload(BaseModel):
    id: str
    thread_id: str
    kind: str
    content: str
    created_at: str
    metadata: AgentRunMetadataPayload | None = None


class InteractionPagePayload(BaseModel):
    messages: list[InteractionPayload]
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
