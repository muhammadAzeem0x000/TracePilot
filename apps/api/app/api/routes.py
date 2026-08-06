from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.ai.embeddings import EmbeddingProviderError
from app.ai.provider import LLMProviderError
from app.api.dependencies import (
    IncidentServiceDependency,
    InvestigationServiceDependency,
    KnowledgeRetrievalServiceDependency,
    MutationEnabledDependency,
)
from app.config.settings import Settings, get_settings
from app.schemas.evidence import EvidenceListResponse
from app.schemas.incident import (
    ErrorResponse,
    HealthResponse,
    IncidentCreate,
    IncidentListResponse,
    IncidentResponse,
    PublicConfigResponse,
    RepositoryFullName,
)
from app.schemas.investigation import (
    InvestigationAcceptedResponse,
    InvestigationListResponse,
    InvestigationResponse,
    InvestigationReviewCreate,
    InvestigationReviewResponse,
)
from app.schemas.knowledge import KnowledgeSearchMode, KnowledgeSearchResponse
from app.schemas.operations import InvestigationMetricsResponse
from app.services.incidents import IncidentNotFoundError
from app.services.investigations import (
    InvestigationNotFoundError,
    InvestigationReviewNotAllowedError,
    RepositoryContextRequiredError,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="tracepilot-api", timestamp=datetime.now(UTC))


@router.get("/api/v1/config", response_model=PublicConfigResponse, tags=["system"])
def public_config(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PublicConfigResponse:
    return PublicConfigResponse(
        public_demo_mode=settings.public_demo_mode,
        mutations_enabled=not settings.public_demo_mode,
    )


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
    _mutations_enabled: MutationEnabledDependency,
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
    response_model=InvestigationAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    tags=["investigations"],
)
async def run_investigation(
    incident_id: UUID,
    service: InvestigationServiceDependency,
    _mutations_enabled: MutationEnabledDependency,
) -> InvestigationAcceptedResponse:
    try:
        return await service.enqueue(incident_id)
    except IncidentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} was not found",
        ) from exc
    except RepositoryContextRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


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


@router.get(
    "/api/v1/investigations/{investigation_id}/metrics",
    response_model=InvestigationMetricsResponse,
    responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["investigations"],
)
async def get_investigation_metrics(
    investigation_id: UUID,
    service: InvestigationServiceDependency,
) -> InvestigationMetricsResponse:
    try:
        return await service.metrics(investigation_id)
    except InvestigationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {investigation_id} was not found",
        ) from exc


@router.post(
    "/api/v1/investigations/{investigation_id}/review",
    response_model=InvestigationReviewResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    tags=["investigations"],
)
async def review_investigation(
    investigation_id: UUID,
    review: InvestigationReviewCreate,
    service: InvestigationServiceDependency,
    _mutations_enabled: MutationEnabledDependency,
) -> InvestigationReviewResponse:
    try:
        return await service.review(investigation_id, review)
    except InvestigationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {investigation_id} was not found",
        ) from exc
    except InvestigationReviewNotAllowedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get(
    "/api/v1/knowledge/search",
    response_model=KnowledgeSearchResponse,
    responses={502: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    tags=["knowledge-debug"],
)
async def search_knowledge(
    service: KnowledgeRetrievalServiceDependency,
    q: Annotated[str, Query(min_length=3, max_length=500)],
    repository: Annotated[RepositoryFullName, Query()],
    mode: KnowledgeSearchMode = KnowledgeSearchMode.HYBRID,
    top_k: int = Query(default=5, ge=1, le=10),
) -> KnowledgeSearchResponse:
    try:
        return await service.search(q, repository, mode, top_k)
    except (EmbeddingProviderError, LLMProviderError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Knowledge retrieval provider is temporarily unavailable",
        ) from exc
