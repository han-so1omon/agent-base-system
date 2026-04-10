from __future__ import annotations

from base_agent_system.evaluations.models import EvaluationRun, MetricResult
from base_agent_system.evaluations.registry import MetricRegistry


def test_metric_registry_registers_and_runs_applicable_metrics() -> None:
    from base_agent_system.evaluations.metrics import EvaluationMetric

    class _GroundingMetric(EvaluationMetric):
        metric_name = "grounding.support"
        metric_version = "v1"

        def applies_to(self, run: EvaluationRun) -> bool:
            return run.primitive_signals.get("citation_count", 0) > 0

        def score(self, run: EvaluationRun) -> MetricResult:
            return MetricResult(
                metric_name=self.metric_name,
                metric_version=self.metric_version,
                score=0.9,
                reason="citations present",
                details={"citation_count": run.primitive_signals["citation_count"]},
            )

    class _EfficiencyMetric(EvaluationMetric):
        metric_name = "efficiency.tool_cost"
        metric_version = "v1"

        def applies_to(self, run: EvaluationRun) -> bool:
            return True

        def score(self, run: EvaluationRun) -> MetricResult:
            return MetricResult(
                metric_name=self.metric_name,
                metric_version=self.metric_version,
                score=0.7,
                reason="few tool calls",
                details={"tool_call_count": run.primitive_signals["tool_call_count"]},
            )

    registry = MetricRegistry()
    registry.register(_GroundingMetric())
    registry.register(_EfficiencyMetric())

    run = EvaluationRun(
        thread_id="thread-123",
        interaction_id="interaction-456",
        parent_interaction_id=None,
        answer="Supported answer",
        primitive_signals={"citation_count": 2, "tool_call_count": 1},
    )

    results = registry.evaluate(run)

    assert results == [
        MetricResult(
            metric_name="grounding.support",
            metric_version="v1",
            score=0.9,
            reason="citations present",
            details={"citation_count": 2},
        ),
        MetricResult(
            metric_name="efficiency.tool_cost",
            metric_version="v1",
            score=0.7,
            reason="few tool calls",
            details={"tool_call_count": 1},
        ),
    ]


def test_metric_registry_skips_non_applicable_metrics() -> None:
    from base_agent_system.evaluations.metrics import EvaluationMetric

    class _GroundingMetric(EvaluationMetric):
        metric_name = "grounding.support"
        metric_version = "v2"

        def applies_to(self, run: EvaluationRun) -> bool:
            return run.primitive_signals.get("citation_count", 0) > 0

        def score(self, run: EvaluationRun) -> MetricResult:
            raise AssertionError("non-applicable metric should not run")

    registry = MetricRegistry()
    registry.register(_GroundingMetric())

    run = EvaluationRun(
        thread_id="thread-123",
        interaction_id="interaction-789",
        parent_interaction_id="interaction-111",
        answer="Ungrounded answer",
        primitive_signals={"citation_count": 0, "tool_call_count": 3},
    )

    assert registry.evaluate(run) == []


def test_metric_results_keep_primitive_signals_separate() -> None:
    run = EvaluationRun(
        thread_id="thread-123",
        interaction_id="interaction-000",
        parent_interaction_id=None,
        answer="Answer",
        primitive_signals={"citation_count": 1, "latency_ms": 1200},
    )

    assert run.primitive_signals == {"citation_count": 1, "latency_ms": 1200}
