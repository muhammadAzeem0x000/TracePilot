"""Opt-in live verification of retrieval and a knowledge-grounded investigation."""

import argparse
import asyncio
import json
from datetime import UTC, datetime

from app.ai.embeddings import GeminiEmbeddingProvider
from app.ai.provider import OpenAICompatibleLLMProvider
from app.config.settings import Settings
from app.db.supabase import SupabaseRestClient
from app.integrations.github import GitHubClient
from app.repositories.evidence import SupabaseEvidenceRepository
from app.repositories.incidents import SupabaseIncidentRepository
from app.repositories.investigations import SupabaseInvestigationRepository
from app.repositories.knowledge import SupabaseKnowledgeRepository
from app.retrieval.context import ContextAssembler
from app.retrieval.reranking import KnowledgeReranker
from app.retrieval.service import KnowledgeRetrievalService
from app.schemas.evidence import EvidenceSourceType
from app.schemas.incident import IncidentCreate, Severity
from app.schemas.knowledge import KnowledgeSearchMode
from app.services.incidents import IncidentService
from app.services.investigations import InvestigationService
from app.tools.github import GitHubToolExecutor
from app.tools.investigation import InvestigationToolExecutor
from app.tools.knowledge import KnowledgeToolExecutor


async def verify(repository_full_name: str) -> dict[str, object]:
    settings = Settings()
    supabase_url, supabase_key = settings.require_supabase()
    github_url, github_token = settings.require_github()
    llm_url, llm_key, llm_model = settings.require_llm()
    embedding_url, embedding_key, embedding_model, dimensions = settings.require_embedding()

    storage = SupabaseRestClient(supabase_url, supabase_key)
    incidents = SupabaseIncidentRepository(storage)
    investigations = SupabaseInvestigationRepository(storage)
    evidence = SupabaseEvidenceRepository(storage)
    knowledge = SupabaseKnowledgeRepository(storage)
    llm = OpenAICompatibleLLMProvider(llm_url, llm_key, llm_model)
    embeddings = GeminiEmbeddingProvider(
        embedding_url,
        embedding_key,
        embedding_model,
        dimensions,
    )
    retrieval = KnowledgeRetrievalService(
        knowledge,
        embeddings,
        ContextAssembler(settings.knowledge_context_budget_tokens),
        candidate_limit=settings.knowledge_candidate_limit,
        reranker=KnowledgeReranker(llm) if settings.knowledge_rerank_enabled else None,
    )

    preflight = await retrieval.search(
        "checkout failures after deployment with a missing database column",
        repository_full_name,
        KnowledgeSearchMode.RERANKED,
        top_k=5,
    )
    if not preflight.items:
        raise RuntimeError("Knowledge retrieval preflight returned no chunks")

    incident = await IncidentService(incidents).create(
        IncidentCreate(
            title="Checkout HTTP 500 after deployment",
            description=(
                "Production checkout references payment_status, but the database column appears "
                "missing after deployment. Search repository knowledge for the applicable runbook "
                "and prior incident before forming a preliminary hypothesis."
            ),
            severity=Severity.HIGH,
            started_at=datetime.now(UTC),
            repository_full_name=repository_full_name,
        )
    )
    service = InvestigationService(
        incidents,
        investigations,
        evidence,
        InvestigationToolExecutor(
            GitHubToolExecutor(GitHubClient(github_url, github_token), evidence),
            KnowledgeToolExecutor(retrieval, evidence),
        ),
        llm,
        max_tool_calls=settings.max_tool_calls,
        final_output_retries=settings.final_output_retries,
    )
    investigation = await service.run(incident.id)
    collected = await evidence.list_for_investigation(investigation.id)
    knowledge_evidence = [
        item for item in collected if item.source_type is EvidenceSourceType.KNOWLEDGE_CHUNK
    ]
    cited = set(investigation.supporting_evidence_ids)
    valid = await evidence.ids_for_context(incident.id, investigation.id, cited)
    cited_knowledge = [item for item in knowledge_evidence if item.id in cited]

    if investigation.status.value != "completed":
        raise RuntimeError("Investigation did not complete")
    if not knowledge_evidence:
        raise RuntimeError("The model did not execute search_knowledge")
    if cited != valid:
        raise RuntimeError("Investigation contains an invalid evidence citation")
    if not cited_knowledge:
        raise RuntimeError("Investigation did not cite persisted knowledge Evidence")

    return {
        "repository": repository_full_name,
        "incident_id": str(incident.id),
        "investigation_id": str(investigation.id),
        "status": investigation.status.value,
        "embedding_model": embeddings.model_name,
        "embedding_dimensions": embeddings.dimensions,
        "preflight_sources": [item.source_reference for item in preflight.items],
        "preflight_rerank_fallback": preflight.rerank_fallback,
        "evidence_count": len(collected),
        "knowledge_evidence_count": len(knowledge_evidence),
        "cited_knowledge_evidence_count": len(cited_knowledge),
        "all_citations_valid": cited == valid,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    arguments = parser.parse_args()
    print(json.dumps(asyncio.run(verify(arguments.repository)), indent=2))


if __name__ == "__main__":
    main()
