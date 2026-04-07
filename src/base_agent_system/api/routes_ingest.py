"""Ingest API route."""

from fastapi import APIRouter, HTTPException, Request, status

from base_agent_system.api.models import IngestRequest, IngestResponse

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest, request: Request) -> IngestResponse:
    ingest_service = request.app.state.runtime_state.ingest_service
    if ingest_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ingest service is unavailable",
        )

    path = payload.path or str(request.app.state.runtime_state.settings.docs_seed_path)
    result = ingest_service.run(path=path)
    return IngestResponse.model_validate(result)
