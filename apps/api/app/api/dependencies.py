from typing import Annotated

from fastapi import Depends

from app.ai.provider import LLMProvider, OpenAICompatibleLLMProvider
from app.config.settings import Settings, get_settings
from app.db.supabase import SupabaseRestClient
from app.integrations.github import GitHubClient, GitHubClientProtocol
from app.repositories.evidence import EvidenceRepository, SupabaseEvidenceRepository
from app.repositories.incidents import IncidentRepository, SupabaseIncidentRepository
from app.repositories.investigations import (
    InvestigationRepository,
    SupabaseInvestigationRepository,
)
from app.services.incidents import IncidentService
from app.services.investigations import InvestigationService
from app.tools.github import GitHubToolExecutor


def get_storage_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SupabaseRestClient:
    project_url, api_key = settings.require_supabase()
    return SupabaseRestClient(project_url, api_key)


def get_incident_repository(
    client: Annotated[SupabaseRestClient, Depends(get_storage_client)],
) -> IncidentRepository:
    return SupabaseIncidentRepository(client)


def get_evidence_repository(
    client: Annotated[SupabaseRestClient, Depends(get_storage_client)],
) -> EvidenceRepository:
    return SupabaseEvidenceRepository(client)


def get_investigation_repository(
    client: Annotated[SupabaseRestClient, Depends(get_storage_client)],
) -> InvestigationRepository:
    return SupabaseInvestigationRepository(client)


def get_github_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> GitHubClientProtocol:
    api_url, token = settings.require_github()
    return GitHubClient(api_url, token)


def get_llm_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LLMProvider:
    base_url, api_key, model = settings.require_llm()
    return OpenAICompatibleLLMProvider(base_url, api_key, model)


def get_incident_service(
    repository: Annotated[IncidentRepository, Depends(get_incident_repository)],
) -> IncidentService:
    return IncidentService(repository)


IncidentServiceDependency = Annotated[IncidentService, Depends(get_incident_service)]


def get_investigation_service(
    incidents: Annotated[IncidentRepository, Depends(get_incident_repository)],
    investigations: Annotated[
        InvestigationRepository,
        Depends(get_investigation_repository),
    ],
    evidence: Annotated[EvidenceRepository, Depends(get_evidence_repository)],
    github: Annotated[GitHubClientProtocol, Depends(get_github_client)],
    llm: Annotated[LLMProvider, Depends(get_llm_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InvestigationService:
    return InvestigationService(
        incidents,
        investigations,
        evidence,
        GitHubToolExecutor(github, evidence),
        llm,
        max_tool_calls=settings.max_tool_calls,
        final_output_retries=settings.final_output_retries,
    )


InvestigationServiceDependency = Annotated[
    InvestigationService,
    Depends(get_investigation_service),
]
