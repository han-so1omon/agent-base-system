"""Workflow execution context."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class WorkflowExecutionContext:
    thread_id: str
    interaction_id: str
    parent_interaction_id: str | None = None
    execution_mode: Literal["foreground", "background"] = "foreground"
    reporting_target: Literal["user", "parent"] = "user"
    context_policy: dict[str, object] = field(default_factory=dict)
    cancellation_requested: bool = False
