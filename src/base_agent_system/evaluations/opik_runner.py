"""Helpers for running curated Opik evaluations."""

from __future__ import annotations

from dataclasses import dataclass, field

from base_agent_system.evaluations.models import EvaluationRun, MetricResult
from base_agent_system.evaluations.registry import MetricRegistry


@dataclass(frozen=True)
class CuratedExample:
    thread_id: str
    interaction_id: str
    answer: str
    primitive_signals: dict[str, object] = field(default_factory=dict)
    parent_interaction_id: str | None = None


class OpikEvaluationRunner:
    def __init__(self, *, metric_registry: MetricRegistry, opik_client: object | None = None) -> None:
        self._metric_registry = metric_registry
        self._opik_client = opik_client

    def run(self, *, experiment_name: str, examples: list[CuratedExample]) -> list[dict[str, object]]:
        rows = [self._evaluate_example(example) for example in examples]
        if self._opik_client is not None:
            self._opik_client.log_experiment(experiment_name=experiment_name, rows=rows)
        return rows

    def _evaluate_example(self, example: CuratedExample) -> dict[str, object]:
        run = EvaluationRun(
            thread_id=example.thread_id,
            interaction_id=example.interaction_id,
            parent_interaction_id=example.parent_interaction_id,
            answer=example.answer,
            primitive_signals=dict(example.primitive_signals),
        )
        metric_results = self._metric_registry.evaluate(run)
        return {
            "thread_id": run.thread_id,
            "interaction_id": run.interaction_id,
            "parent_interaction_id": run.parent_interaction_id,
            "answer": run.answer,
            "primitive_signals": run.primitive_signals,
            "metrics": [_serialize_metric_result(result) for result in metric_results],
        }


def _serialize_metric_result(result: MetricResult) -> dict[str, object]:
    return {
        "metric_name": result.metric_name,
        "metric_version": result.metric_version,
        "score": result.score,
        "reason": result.reason,
        "details": result.details,
    }
