"""Thread browsing API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from base_agent_system.api.models import (
    DebugInteractionPayload,
    InteractionEventPagePayload,
    InteractionEventPayload,
    InteractionPagePayload,
    ThreadSummaryPayload,
)

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
    page = repository.list_thread_interactions(
        thread_id=thread_id,
        limit=limit,
        before_ts=before_ts,
        before_id=before_id,
    )
    if isinstance(page, dict):
        return InteractionPagePayload.model_validate(page)
    return InteractionPagePayload(
        items=[_interaction_payload(item) for item in page.items],
        has_more=page.has_more,
        next_before=page.next_before,
    )


@router.get("/interactions/{interaction_id}/children", response_model=InteractionPagePayload)
def list_child_interactions(
    interaction_id: str,
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
) -> InteractionPagePayload:
    repository = _get_interaction_repository(request)
    page = repository.list_child_interactions(parent_interaction_id=interaction_id, limit=limit)
    if isinstance(page, dict):
        return InteractionPagePayload.model_validate(page)
    return InteractionPagePayload(
        items=[_interaction_payload(item) for item in page.items],
        has_more=page.has_more,
        next_before=page.next_before,
    )


@router.get("/interactions/{interaction_id}/events", response_model=InteractionEventPagePayload)
def list_interaction_events(
    interaction_id: str,
    request: Request,
    limit: int = Query(default=20, ge=1, le=200),
    before_ts: str | None = None,
    before_id: str | None = None,
) -> InteractionEventPagePayload:
    repository = _get_interaction_repository(request)
    page = repository.list_interaction_events(
        interaction_id=interaction_id,
        limit=limit,
        before_ts=before_ts,
        before_id=before_id,
    )
    if isinstance(page, dict):
        return InteractionEventPagePayload.model_validate(page)
    return InteractionEventPagePayload(
        items=[_interaction_event_payload(item) for item in page.items],
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


def _interaction_payload(item) -> dict[str, object]:
    metadata = item.metadata
    return {
        "id": item.id,
        "thread_id": item.thread_id,
        "parent_interaction_id": item.parent_interaction_id,
        "kind": item.kind,
        "status": item.status,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "last_event_at": item.last_event_at,
        "latest_display_event_id": item.latest_display_event_id,
        "child_count": item.child_count,
        "latest_display_event": None if item.latest_display_event is None else _interaction_event_payload(item.latest_display_event),
        "metadata": _interaction_metadata(metadata),
    }


def _interaction_event_payload(item) -> dict[str, object]:
    return InteractionEventPayload(
        id=item.id,
        interaction_id=item.interaction_id,
        event_type=item.event_type,
        created_at=item.created_at,
        content=item.content,
        is_display_event=item.is_display_event,
        status=item.status,
        metadata=item.metadata,
        artifacts=[artifact.__dict__ for artifact in (item.artifacts or [])],
    ).model_dump()


def _interaction_metadata(metadata: object) -> dict[str, object] | None:
    if metadata is None:
        return None
    if hasattr(metadata, "used_tools"):
        return {
            "used_tools": metadata.used_tools,
            "tool_call_count": metadata.tool_call_count,
            "tools_used": metadata.tools_used,
        }
    if isinstance(metadata, dict):
        return metadata
    return None
