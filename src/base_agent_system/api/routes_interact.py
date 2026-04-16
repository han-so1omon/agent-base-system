"""Canonical interaction API route."""

from fastapi import APIRouter, HTTPException, Request, status

from base_agent_system.api.models import InteractRequest, InteractResponse

router = APIRouter()


@router.post("/interact", response_model=InteractResponse)
def interact(payload: InteractRequest, request: Request) -> InteractResponse:
    with request.app.state.runtime_state.observability_service.start_span(
        name="POST /interact",
        metadata={"thread_id": payload.thread_id},
    ):
        result = run_interaction(
            workflow_service=request.app.state.runtime_state.workflow_service,
            thread_id=payload.thread_id,
            messages=[message.model_dump() for message in payload.messages],
        )
        return InteractResponse.model_validate(result)



def run_interaction(*, workflow_service: object | None, thread_id: str, messages: list[dict[str, str]]) -> dict[str, object]:
    if workflow_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="workflow service is unavailable",
        )
    return workflow_service.run(thread_id=thread_id, messages=messages)
