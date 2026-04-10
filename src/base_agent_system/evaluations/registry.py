"""Registry for pluggable evaluation metrics."""

from __future__ import annotations

from base_agent_system.evaluations.metrics import EvaluationMetric
from base_agent_system.evaluations.models import EvaluationRun, MetricResult


class MetricRegistry:
    def __init__(self) -> None:
        self._metrics: list[EvaluationMetric] = []

    def register(self, metric: EvaluationMetric) -> None:
        self._metrics.append(metric)

    def evaluate(self, run: EvaluationRun) -> list[MetricResult]:
        results: list[MetricResult] = []
        for metric in self._metrics:
            if metric.applies_to(run):
                results.append(metric.score(run))
        return results
