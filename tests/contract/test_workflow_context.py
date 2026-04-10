from __future__ import annotations


def test_workflow_execution_context_tracks_branch_and_policy_fields() -> None:
    from base_agent_system.workflow.context import WorkflowExecutionContext

    context = WorkflowExecutionContext(
        thread_id="thread-123",
        interaction_id="interaction-123",
        parent_interaction_id="interaction-parent",
        execution_mode="background",
        reporting_target="parent",
        context_policy={"seed_thread_ids": ["thread-a"], "graph_expansion": "allowed"},
        cancellation_requested=False,
    )

    assert context.thread_id == "thread-123"
    assert context.execution_mode == "background"
    assert context.reporting_target == "parent"
    assert context.context_policy == {"seed_thread_ids": ["thread-a"], "graph_expansion": "allowed"}


def test_workflow_execution_context_defaults_to_foreground_user_reporting() -> None:
    from base_agent_system.workflow.context import WorkflowExecutionContext

    context = WorkflowExecutionContext(thread_id="thread-123", interaction_id="interaction-123")

    assert context.parent_interaction_id is None
    assert context.execution_mode == "foreground"
    assert context.reporting_target == "user"
    assert context.context_policy == {}
    assert context.cancellation_requested is False
