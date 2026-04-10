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

    repository.append_event(
        interaction_id=interaction_id,
        event_type="started",
        content="Delegated interaction started.",
        is_display_event=True,
        status="running",
    )
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
    return result
