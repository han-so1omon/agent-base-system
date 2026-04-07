"""Small workflow state shared across LangGraph nodes."""

from __future__ import annotations

from typing import Any, TypedDict


class WorkflowState(TypedDict, total=False):
    thread_id: str
    query: str
    retrieved_docs: list[dict[str, Any]]
    retrieved_memory: list[dict[str, Any]]
    answer: str
    citations: list[dict[str, str]]
    debug: dict[str, int]
