"""Background interaction execution tasks."""

from __future__ import annotations


async def run_interaction_branch(
    context,
    *,
    thread_id: str,
    interaction_id: str,
    parent_interaction_id: str | None = None,
) -> dict[str, object]:
    repository = context.runtime_state.interaction_repository
    workflow_service = context.runtime_state.workflow_service
    observability_service = getattr(context.runtime_state, "observability_service", None)
    branch_trace = (
        observability_service.start_branch_trace(
            name="worker_interaction_branch",
            metadata={
                "thread_id": thread_id,
                "interaction_id": interaction_id,
                "parent_interaction_id": parent_interaction_id,
                "branch_kind": "child" if parent_interaction_id is not None else "root",
            },
        )
        if observability_service is not None
        else _NoopTraceContext()
    )

    with branch_trace as trace:
        repository.append_event(
            interaction_id=interaction_id,
            event_type="started",
            content="Delegated interaction started.",
            is_display_event=True,
            status="running",
        )
        try:
            result = await workflow_service.arun(
                thread_id=thread_id,
                interaction_id=interaction_id,
                parent_interaction_id=parent_interaction_id,
            )
            repository.append_event(
                interaction_id=interaction_id,
                event_type="completed",
                content=result["answer"],
                is_display_event=True,
                status="completed",
            )
            if parent_interaction_id is not None:
                repository.append_event(
                    interaction_id=parent_interaction_id,
                    event_type="child_summary",
                    content=result["answer"],
                    is_display_event=True,
                    status="running",
                    metadata={"child_interaction_id": interaction_id},
                )
            trace.metadata["status"] = "completed"
            return result
        except Exception:
            trace.metadata["status"] = "failed"
            raise


class _NoopTraceContext:
    def __enter__(self):
        return type("TraceHandle", (), {"metadata": {}})()

    def __exit__(self, exc_type, exc, tb) -> None:
        return None
