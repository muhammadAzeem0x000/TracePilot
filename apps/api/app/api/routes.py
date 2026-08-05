from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import IncidentServiceDependency, InvestigationServiceDependency
from app.schemas.evidence import EvidenceListResponse
from app.schemas.incident import (
    ErrorResponse,
    HealthResponse,
    IncidentCreate,
    IncidentListResponse,
    IncidentResponse,
)
from app.schemas.investigation import InvestigationListResponse, InvestigationResponse
from app.services.incidents import IncidentNotFoundError
from app.services.investigations import (
    InvestigationExecutionError,
    InvestigationNotFoundError,
    RepositoryContextRequiredError,
)

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


@router.post(
    "/api/v1/incidents/{incident_id}/investigations",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    tags=["investigations"],
)
async def run_investigation(
    incident_id: UUID,
    service: InvestigationServiceDependency,
) -> InvestigationResponse:
    try:
        return await service.run(incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} was not found",
        ) from exc
    except RepositoryContextRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvestigationExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": str(exc), "investigation_id": str(exc.investigation_id)},
        ) from exc


@router.get(
    "/api/v1/incidents/{incident_id}/evidence",
    response_model=EvidenceListResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["evidence"],
)
async def list_evidence(
    incident_id: UUID,
    service: InvestigationServiceDependency,
) -> EvidenceListResponse:
    try:
        return await service.list_evidence(incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} was not found",
        ) from exc


@router.get(
    "/api/v1/incidents/{incident_id}/investigations",
    response_model=InvestigationListResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["investigations"],
)
async def list_investigations(
    incident_id: UUID,
    service: InvestigationServiceDependency,
) -> InvestigationListResponse:
    try:
        return await service.list_for_incident(incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} was not found",
        ) from exc


@router.get(
    "/api/v1/investigations/{investigation_id}",
    response_model=InvestigationResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["investigations"],
)
async def get_investigation(
    investigation_id: UUID,
    service: InvestigationServiceDependency,
) -> InvestigationResponse:
    try:
        return await service.get(investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {investigation_id} was not found",
        ) from exc
