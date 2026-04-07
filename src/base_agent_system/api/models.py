"""API request and response models."""

from typing import Literal

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: Literal["ok", "unavailable"]


class CitationPayload(BaseModel):
    source: str
    snippet: str


class QueryRequest(BaseModel):
    thread_id: str
    query: str


class QueryResponse(BaseModel):
    thread_id: str
    answer: str
    citations: list[CitationPayload]
    debug: dict[str, int]


class IngestRequest(BaseModel):
    path: str | None = None


class IngestResponse(BaseModel):
    file_count: int
    chunk_count: int
