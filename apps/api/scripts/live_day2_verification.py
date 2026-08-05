"""Opt-in live verification using configured Supabase, GitHub, and LLM services."""

import argparse
import asyncio
import json
from datetime import UTC, datetime

from app.ai.provider import OpenAICompatibleLLMProvider
from app.config.settings import Settings
from app.db.supabase import SupabaseRestClient
from app.integrations.github import GitHubClient
from app.repositories.evidence import SupabaseEvidenceRepository
from app.repositories.incidents import SupabaseIncidentRepository
from app.repositories.investigations import SupabaseInvestigationRepository
from app.schemas.incident import IncidentCreate, Severity
from app.services.incidents import IncidentService
from app.services.investigations import InvestigationService
from app.tools.github import GitHubToolExecutor


async def verify(repository_full_name: str) -> dict[str, object]:
    settings = Settings()
    supabase_url, supabase_key = settings.require_supabase()
    github_url, github_token = settings.require_github()
    llm_url, llm_key, llm_model = settings.require_llm()

    storage = SupabaseRestClient(supabase_url, supabase_key)
    incidents = SupabaseIncidentRepository(storage)
    evidence = SupabaseEvidenceRepository(storage)
    investigations = SupabaseInvestigationRepository(storage)
    github = GitHubClient(github_url, github_token)
    llm = OpenAICompatibleLLMProvider(llm_url, llm_key, llm_model)

    github_preflight = await github.list_recent_commits(
        repository_full_name,
        since=None,
        limit=1,
    )
    if not github_preflight:
        raise RuntimeError("GitHub preflight returned no commits")

    incident = await IncidentService(incidents).create(
        IncidentCreate(
            title="TracePilot Day-2 live verification",
            description=(
                "Verify that recent repository changes can be collected as evidence and "
                "used for a preliminary, structured investigation."
            ),
            severity=Severity.MEDIUM,
            started_at=datetime.now(UTC),
            repository_full_name=repository_full_name,
        )
    )
    service = InvestigationService(
        incidents,
        investigations,
        evidence,
        GitHubToolExecutor(github, evidence),
        llm,
        max_tool_calls=settings.max_tool_calls,
        final_output_retries=settings.final_output_retries,
    )
    investigation = await service.run(incident.id)
    collected = await evidence.list_for_investigation(investigation.id)
    cited = set(investigation.supporting_evidence_ids)
    validated = await evidence.ids_for_context(incident.id, investigation.id, cited)

    if not collected:
        raise RuntimeError("Investigation completed without persisted evidence")
    if investigation.status.value != "completed":
        raise RuntimeError("Investigation did not complete")
    if cited != validated:
        raise RuntimeError("Investigation contains an invalid evidence reference")

    return {
        "repository": repository_full_name,
        "github_preflight_sha": github_preflight[0].sha,
        "incident_id": str(incident.id),
        "investigation_id": str(investigation.id),
        "status": investigation.status.value,
        "model": investigation.model_name,
        "evidence_count": len(collected),
        "source_types": sorted({item.source_type.value for item in collected}),
        "cited_evidence_count": len(cited),
        "all_citations_valid": cited == validated,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository",
        default="openai/openai-python",
        help="GitHub repository in owner/name format",
    )
    arguments = parser.parse_args()
    result = asyncio.run(verify(arguments.repository))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
