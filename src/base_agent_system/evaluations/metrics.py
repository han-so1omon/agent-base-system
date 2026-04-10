"""Metric interfaces for branch evaluation."""

from __future__ import annotations

from typing import Protocol

from base_agent_system.evaluations.models import EvaluationRun, MetricResult


class EvaluationMetric(Protocol):
    metric_name: str
    metric_version: str

    def applies_to(self, run: EvaluationRun) -> bool: ...

    def score(self, run: EvaluationRun) -> MetricResult: ...
