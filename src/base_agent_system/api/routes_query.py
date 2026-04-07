"""Query API route."""

from fastapi import APIRouter, HTTPException, Request, status

from base_agent_system.api.models import QueryRequest, QueryResponse

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest, request: Request) -> QueryResponse:
    workflow_service = request.app.state.runtime_state.workflow_service
    if workflow_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="workflow service is unavailable",
        )

    result = workflow_service.run(thread_id=payload.thread_id, query=payload.query)
    return QueryResponse.model_validate(result)
