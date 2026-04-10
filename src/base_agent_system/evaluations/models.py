"""Evaluation domain models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvaluationRun:
    thread_id: str
    interaction_id: str
    parent_interaction_id: str | None
    answer: str
    primitive_signals: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricResult:
    metric_name: str
    metric_version: str
    score: float
    reason: str
    details: dict[str, object] | None = None
