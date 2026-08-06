"""Opt-in live verification of Day-5 traces against real providers and Supabase."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from app.config.settings import Settings
from app.db.supabase import SupabaseRestClient
from app.repositories.evidence import SupabaseEvidenceRepository
from app.repositories.incidents import SupabaseIncidentRepository
from app.schemas.evidence import EvidenceSourceType
from app.schemas.incident import IncidentCreate, Severity
from app.services.incidents import IncidentService
from app.services.runtime import build_investigation_runtime


async def verify(repository_full_name: str) -> dict[str, object]:
    settings = Settings()
    supabase_url, supabase_key = settings.require_supabase()
    storage = SupabaseRestClient(supabase_url, supabase_key)
    incidents = IncidentService(SupabaseIncidentRepository(storage))
    evidence_repository = SupabaseEvidenceRepository(storage)
    active = await storage.request(
        "GET",
        "/investigation_jobs",
        params={"select": "id", "status": "in.(queued,running,retry_scheduled)"},
    )
    if active:
        raise RuntimeError("Live trace verification requires an idle investigation queue")

    incident = await incidents.create(
        IncidentCreate(
            title="[Day 5 live] Duplicate refunds after worker restart",
            description=(
                "A small group of customers received duplicate refunds when workers restarted "
                "during a provider slowdown. Use the repository knowledge and recent read-only "
                "GitHub evidence to identify the most plausible change."
            ),
            severity=Severity.HIGH,
            started_at=datetime.now(UTC),
            repository_full_name=repository_full_name,
        )
    )
    runtime = build_investigation_runtime(settings)
    accepted = await runtime.service.enqueue(incident.id)
    processed = await runtime.worker.run_once()
    if not processed:
        raise RuntimeError("The worker did not claim the verification investigation")
    investigation = await runtime.service.get(accepted.investigation_id)
    if investigation.status.value != "completed":
        raise RuntimeError(f"Investigation ended as {investigation.status.value}")

    evidence = await evidence_repository.list_for_investigation(investigation.id)
    knowledge = [
        item for item in evidence if item.source_type is EvidenceSourceType.KNOWLEDGE_CHUNK
    ]
    if not knowledge:
        raise RuntimeError("The live model did not invoke search_knowledge")
    cited = set(investigation.supporting_evidence_ids)
    valid = await evidence_repository.ids_for_context(incident.id, investigation.id, cited)
    if cited != valid:
        raise RuntimeError("A persisted investigation citation failed ownership validation")
    metrics = await runtime.service.metrics(investigation.id)
    operation_types = {item.operation_type.value for item in metrics.operations}
    required = {"queue_wait", "investigation", "llm_call", "knowledge_retrieval", "embedding"}
    missing = required - operation_types
    if missing:
        raise RuntimeError(f"Missing required live operation traces: {sorted(missing)}")

    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "incident_id": str(incident.id),
        "investigation_id": str(investigation.id),
        "repository": repository_full_name,
        "status": investigation.status.value,
        "tool_call_count": investigation.tool_call_count,
        "evidence_count": len(evidence),
        "knowledge_evidence_ids": [str(item.id) for item in knowledge],
        "cited_evidence_ids": [str(item) for item in investigation.supporting_evidence_ids],
        "all_citations_valid": cited == valid,
        "operation_count": len(metrics.operations),
        "operation_types": sorted(operation_types),
        "latency": [item.model_dump(mode="json") for item in metrics.latency],
        "input_tokens": metrics.input_tokens,
        "output_tokens": metrics.output_tokens,
        "total_tokens": metrics.total_tokens,
        "estimated_cost_usd": metrics.estimated_cost_usd,
        "cost_status": metrics.cost_status,
        "fallback_used": metrics.fallback_used,
        "serving_providers": metrics.serving_providers,
        "serving_models": metrics.serving_models,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", type=Path, default=Path("docs/evaluation/day5_live_trace.json"))
    arguments = parser.parse_args()
    result = asyncio.run(verify(arguments.repository))
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
