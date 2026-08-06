from dataclasses import dataclass

from app.ai.embeddings import GeminiEmbeddingProvider
from app.ai.provider import FallbackLLMProvider, LLMProvider, OpenAICompatibleLLMProvider
from app.config.settings import Settings
from app.db.supabase import SupabaseRestClient
from app.integrations.github import GitHubClient
from app.observability.pricing import PricingRegistry
from app.observability.providers import ObservedEmbeddingProvider, ObservedLLMProvider
from app.observability.tools import ObservedInvestigationToolExecutor
from app.repositories.evidence import SupabaseEvidenceRepository
from app.repositories.incidents import SupabaseIncidentRepository
from app.repositories.investigations import SupabaseInvestigationRepository
from app.repositories.jobs import SupabaseInvestigationJobRepository
from app.repositories.knowledge import SupabaseKnowledgeRepository
from app.repositories.operations import SupabaseAIOperationRepository
from app.repositories.reviews import SupabaseInvestigationReviewRepository
from app.retrieval.context import ContextAssembler
from app.retrieval.reranking import KnowledgeReranker
from app.retrieval.service import KnowledgeRetrievalService
from app.services.investigations import InvestigationService
from app.services.worker import InvestigationWorker
from app.tools.github import GitHubToolExecutor
from app.tools.investigation import InvestigationToolExecutor
from app.tools.knowledge import KnowledgeToolExecutor


@dataclass(frozen=True)
class InvestigationRuntime:
    service: InvestigationService
    worker: InvestigationWorker


def build_investigation_runtime(settings: Settings) -> InvestigationRuntime:
    supabase_url, supabase_key = settings.require_supabase()
    github_url, github_token = settings.require_github()
    llm_url, llm_key, llm_model = settings.require_llm()
    embedding_url, embedding_key, embedding_model, dimensions = settings.require_embedding()

    storage = SupabaseRestClient(supabase_url, supabase_key)
    incidents = SupabaseIncidentRepository(storage)
    investigations = SupabaseInvestigationRepository(storage)
    evidence = SupabaseEvidenceRepository(storage)
    jobs = SupabaseInvestigationJobRepository(storage)
    reviews = SupabaseInvestigationReviewRepository(storage)
    operations = SupabaseAIOperationRepository(storage)
    base_llm: LLMProvider = OpenAICompatibleLLMProvider(
        llm_url, llm_key, llm_model, settings.llm_provider_name
    )
    fallback = settings.optional_fallback_llm()
    if fallback is not None:
        fallback_url, fallback_key, fallback_model, fallback_name = fallback
        base_llm = FallbackLLMProvider(
            base_llm,
            OpenAICompatibleLLMProvider(fallback_url, fallback_key, fallback_model, fallback_name),
        )
    llm = ObservedLLMProvider(
        base_llm,
        operations,
        PricingRegistry.from_json(settings.ai_pricing_json, settings.ai_pricing_source_date),
    )
    embeddings = ObservedEmbeddingProvider(
        GeminiEmbeddingProvider(
            embedding_url,
            embedding_key,
            embedding_model,
            dimensions,
        ),
        operations,
    )
    reranker = KnowledgeReranker(llm) if settings.knowledge_rerank_enabled else None
    retrieval = KnowledgeRetrievalService(
        SupabaseKnowledgeRepository(storage),
        embeddings,
        ContextAssembler(settings.knowledge_context_budget_tokens),
        candidate_limit=settings.knowledge_candidate_limit,
        reranker=reranker,
    )
    service = InvestigationService(
        incidents,
        investigations,
        evidence,
        jobs,
        reviews,
        ObservedInvestigationToolExecutor(
            InvestigationToolExecutor(
                GitHubToolExecutor(GitHubClient(github_url, github_token), evidence),
                KnowledgeToolExecutor(retrieval, evidence),
            ),
            operations,
        ),
        llm,
        max_tool_calls=settings.max_tool_calls,
        final_output_retries=settings.final_output_retries,
        max_job_attempts=settings.investigation_job_max_attempts,
        operation_repository=operations,
    )
    return InvestigationRuntime(
        service=service,
        worker=InvestigationWorker(
            jobs,
            service,
            lease_seconds=settings.investigation_job_lease_seconds,
            poll_seconds=settings.investigation_worker_poll_seconds,
            retry_base_seconds=settings.investigation_retry_base_seconds,
        ),
    )
