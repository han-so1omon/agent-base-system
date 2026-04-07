"""Health check routes."""

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from base_agent_system.api.models import HealthStatus
from base_agent_system.dependencies import dependencies_ready

router = APIRouter()


@router.get("/live", response_model=HealthStatus)
def live() -> HealthStatus:
    return HealthStatus(status="ok")


@router.get("/ready", response_model=HealthStatus)
def ready(request: Request) -> HealthStatus | JSONResponse:
    app_state = request.app.state.runtime_state
    if dependencies_ready(app_state):
        return HealthStatus(status="ok")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=HealthStatus(status="unavailable").model_dump(),
    )
