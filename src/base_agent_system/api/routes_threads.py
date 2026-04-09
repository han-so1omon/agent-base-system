"""Thread browsing API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from base_agent_system.api.models import DebugInteractionPayload, InteractionPagePayload, ThreadSummaryPayload

router = APIRouter()


@router.get("/threads", response_model=list[ThreadSummaryPayload])
def list_threads(request: Request, limit: int = Query(default=50, ge=1, le=200)) -> list[ThreadSummaryPayload]:
    repository = _get_interaction_repository(request)
    items = repository.list_threads(limit=limit)
    return [
        ThreadSummaryPayload(
            thread_id=item["thread_id"],
            preview=item["preview"],
        )
        if isinstance(item, dict)
        else ThreadSummaryPayload(thread_id=item.thread_id, preview=item.preview)
        for item in items
    ]


@router.get("/threads/{thread_id}/interactions", response_model=InteractionPagePayload)
def list_interactions(
    thread_id: str,
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
    before_ts: str | None = None,
    before_id: str | None = None,
) -> InteractionPagePayload:
    repository = _get_interaction_repository(request)
    page = repository.list_interactions(
        thread_id=thread_id,
        limit=limit,
        before_ts=before_ts,
        before_id=before_id,
    )
    if isinstance(page, dict):
        return InteractionPagePayload.model_validate(page)
    return InteractionPagePayload(
        messages=[
            {
                "id": item.id,
                "thread_id": item.thread_id,
                "kind": item.kind,
                "content": item.content,
                "created_at": item.created_at,
                "metadata": None
                if item.metadata is None
                else {
                    "used_tools": item.metadata.used_tools,
                    "tool_call_count": item.metadata.tool_call_count,
                    "tools_used": item.metadata.tools_used,
                },
            }
            for item in page.items
        ],
        has_more=page.has_more,
        next_before=page.next_before,
    )


@router.get("/debug/threads/{thread_id}/interactions/{interaction_id}", response_model=DebugInteractionPayload)
def get_debug_interaction(thread_id: str, interaction_id: str, request: Request) -> DebugInteractionPayload:
    settings = request.app.state.runtime_state.settings
    if not getattr(settings, "debug_interactions_enabled", False):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    repository = _get_interaction_repository(request)
    detail = repository.get_debug_interaction(thread_id=thread_id, interaction_id=interaction_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="interaction not found")
    return DebugInteractionPayload.model_validate(detail)


def _get_interaction_repository(request: Request):
    repository = getattr(request.app.state.runtime_state, "interaction_repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="interaction repository is unavailable",
        )
    return repository
