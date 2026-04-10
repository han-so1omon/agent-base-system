"""Interaction control routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status


router = APIRouter()


@router.post("/interactions/{interaction_id}/cancel")
def cancel_interaction(interaction_id: str, request: Request) -> dict[str, object]:
    repository = getattr(request.app.state.runtime_state, "interaction_repository", None)
    if repository is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="interaction repository is unavailable")
    event = repository.request_cancellation(interaction_id=interaction_id)
    return {
        "interaction_id": interaction_id,
        "event_type": event.event_type,
        "status": event.status,
    }
