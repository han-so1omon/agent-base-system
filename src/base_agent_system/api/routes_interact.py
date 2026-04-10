"""Canonical interaction API route."""

import inspect

from fastapi import APIRouter, HTTPException, Request, status

from base_agent_system.api.models import InteractRequest, InteractResponse

router = APIRouter()


@router.post("/interact", response_model=InteractResponse)
def interact(payload: InteractRequest, request: Request) -> InteractResponse:
    result = run_interaction(
        workflow_service=request.app.state.runtime_state.workflow_service,
        thread_id=payload.thread_id,
        messages=[message.model_dump() for message in payload.messages],
        request_metadata={
            "route": "/interact",
            "message_count": len(payload.messages),
            "streaming": False,
            "thread_id": payload.thread_id,
        },
    )
    return InteractResponse.model_validate(result)


def run_interaction(
    *,
    workflow_service: object | None,
    thread_id: str,
    messages: list[dict[str, str]],
    request_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    if workflow_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="workflow service is unavailable",
        )
    run_kwargs = {
        "thread_id": thread_id,
        "messages": messages,
    }
    if request_metadata is not None and _workflow_supports_request_metadata(workflow_service):
        run_kwargs["request_metadata"] = request_metadata
    return workflow_service.run(**run_kwargs)


def _workflow_supports_request_metadata(workflow_service: object) -> bool:
    run_method = getattr(workflow_service, "run", None)
    if run_method is None:
        return False
    try:
        signature = inspect.signature(run_method)
    except (TypeError, ValueError):
        return False
    if "request_metadata" in signature.parameters:
        return True
    return any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values())
