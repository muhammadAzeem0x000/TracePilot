from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import IncidentServiceDependency
from app.schemas.incident import (
    ErrorResponse,
    HealthResponse,
    IncidentCreate,
    IncidentListResponse,
    IncidentResponse,
)
from app.services.incidents import IncidentNotFoundError

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="tracepilot-api", timestamp=datetime.now(UTC))


@router.post(
    "/api/v1/incidents",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={503: {"model": ErrorResponse}},
    tags=["incidents"],
)
async def create_incident(
    incident: IncidentCreate,
    service: IncidentServiceDependency,
) -> IncidentResponse:
    return await service.create(incident)


@router.get(
    "/api/v1/incidents",
    response_model=IncidentListResponse,
    responses={503: {"model": ErrorResponse}},
    tags=["incidents"],
)
async def list_incidents(service: IncidentServiceDependency) -> IncidentListResponse:
    return await service.list()


@router.get(
    "/api/v1/incidents/{incident_id}",
    response_model=IncidentResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["incidents"],
)
async def get_incident(
    incident_id: UUID,
    service: IncidentServiceDependency,
) -> IncidentResponse:
    try:
        return await service.get(incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} was not found",
        ) from exc

