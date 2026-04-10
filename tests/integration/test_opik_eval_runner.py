from __future__ import annotations

from base_agent_system.evaluations.models import EvaluationRun, MetricResult
from base_agent_system.evaluations.registry import MetricRegistry


def test_opik_eval_runner_scores_curated_examples_under_experiment_name() -> None:
    from base_agent_system.evaluations.metrics import EvaluationMetric
    from base_agent_system.evaluations.opik_runner import CuratedExample, OpikEvaluationRunner

    class _CompletionMetric(EvaluationMetric):
        metric_name = "completion.request_resolution"
        metric_version = "v1"

        def applies_to(self, run: EvaluationRun) -> bool:
            return True

        def score(self, run: EvaluationRun) -> MetricResult:
            return MetricResult(
                metric_name=self.metric_name,
                metric_version=self.metric_version,
                score=1.0 if "Kubernetes" in run.answer else 0.0,
                reason="answer mentions target",
                details={"thread_id": run.thread_id},
            )

    registry = MetricRegistry()
    registry.register(_CompletionMetric())
    recorded_calls: list[dict[str, object]] = []

    class _FakeOpikClient:
        def log_experiment(self, *, experiment_name: str, rows: list[dict[str, object]]) -> None:
            recorded_calls.append({"experiment_name": experiment_name, "rows": rows})

    runner = OpikEvaluationRunner(metric_registry=registry, opik_client=_FakeOpikClient())
    examples = [
        CuratedExample(
            thread_id="thread-1",
            interaction_id="interaction-1",
            answer="Preferred target is Kubernetes.",
            primitive_signals={"citation_count": 1, "tool_call_count": 1},
        )
    ]

    results = runner.run(experiment_name="opik-baseline", examples=examples)

    assert results == [
        {
            "thread_id": "thread-1",
            "interaction_id": "interaction-1",
            "parent_interaction_id": None,
            "answer": "Preferred target is Kubernetes.",
            "primitive_signals": {"citation_count": 1, "tool_call_count": 1},
            "metrics": [
                {
                    "metric_name": "completion.request_resolution",
                    "metric_version": "v1",
                    "score": 1.0,
                    "reason": "answer mentions target",
                    "details": {"thread_id": "thread-1"},
                }
            ],
        }
    ]
    assert recorded_calls == [{"experiment_name": "opik-baseline", "rows": results}]
