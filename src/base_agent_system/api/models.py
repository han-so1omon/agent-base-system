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


class IngestRequest(BaseModel):
    path: str | None = None


class IngestResponse(BaseModel):
    file_count: int
    chunk_count: int
