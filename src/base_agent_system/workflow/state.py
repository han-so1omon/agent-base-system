"""Small workflow state shared across LangGraph nodes."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Literal, TypedDict


WorkflowHook = Callable[["WorkflowState"], "WorkflowState"]
WorkflowHookStage = Literal[
    "before_retrieval",
    "after_retrieval",
    "before_answer_synthesis",
    "after_answer_synthesis",
]
WorkflowHooks = dict[WorkflowHookStage, Sequence[WorkflowHook]]


class WorkflowState(TypedDict, total=False):
    thread_id: str
    interaction_id: str
    parent_interaction_id: str | None
    execution_mode: str
    reporting_target: str
    context_policy: dict[str, Any]
    cancellation_requested: bool
    messages: list[dict[str, str]]
    query: str
    retrieved_docs: list[dict[str, Any]]
    retrieved_memory: list[dict[str, Any]]
    answer: str
    citations: list[dict[str, str]]
    debug: dict[str, int]
