from typing import Annotated

from fastapi import Depends

from app.ai.embeddings import EmbeddingProvider, GeminiEmbeddingProvider
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
from app.repositories.knowledge import (
    KnowledgeSearchRepository,
    SupabaseKnowledgeRepository,
)
from app.retrieval.context import ContextAssembler
from app.retrieval.reranking import KnowledgeReranker
from app.retrieval.service import KnowledgeRetrievalService
from app.services.incidents import IncidentService
from app.services.investigations import InvestigationService
from app.tools.github import GitHubToolExecutor
from app.tools.investigation import InvestigationToolExecutor
from app.tools.knowledge import KnowledgeToolExecutor


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


def get_embedding_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmbeddingProvider:
    base_url, api_key, model, dimensions = settings.require_embedding()
    return GeminiEmbeddingProvider(base_url, api_key, model, dimensions)


def get_knowledge_repository(
    client: Annotated[SupabaseRestClient, Depends(get_storage_client)],
) -> KnowledgeSearchRepository:
    return SupabaseKnowledgeRepository(client)


def get_retrieval_service(
    repository: Annotated[KnowledgeSearchRepository, Depends(get_knowledge_repository)],
    embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    llm: Annotated[LLMProvider, Depends(get_llm_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> KnowledgeRetrievalService:
    reranker = KnowledgeReranker(llm) if settings.knowledge_rerank_enabled else None
    return KnowledgeRetrievalService(
        repository,
        embeddings,
        ContextAssembler(settings.knowledge_context_budget_tokens),
        candidate_limit=settings.knowledge_candidate_limit,
        reranker=reranker,
    )


KnowledgeRetrievalServiceDependency = Annotated[
    KnowledgeRetrievalService,
    Depends(get_retrieval_service),
]


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
    retrieval: Annotated[KnowledgeRetrievalService, Depends(get_retrieval_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InvestigationService:
    return InvestigationService(
        incidents,
        investigations,
        evidence,
        InvestigationToolExecutor(
            GitHubToolExecutor(github, evidence),
            KnowledgeToolExecutor(retrieval, evidence),
        ),
        llm,
        max_tool_calls=settings.max_tool_calls,
        final_output_retries=settings.final_output_retries,
    )


InvestigationServiceDependency = Annotated[
    InvestigationService,
    Depends(get_investigation_service),
]
