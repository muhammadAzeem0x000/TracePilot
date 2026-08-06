"""Opt-in live verification for the durable Day-4 investigation queue and API flow."""

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import NoReturn
from uuid import UUID

import httpx

from app.config.settings import Settings
from app.db.supabase import SupabaseRestClient
from app.repositories.incidents import SupabaseIncidentRepository
from app.repositories.investigations import SupabaseInvestigationRepository
from app.repositories.jobs import SupabaseInvestigationJobRepository
from app.schemas.incident import IncidentCreate, Severity
from app.schemas.investigation import InvestigationStage, InvestigationStatus
from app.services.incidents import IncidentService
from app.services.investigation_errors import (
    PermanentInvestigationError,
    RetryableInvestigationError,
)
from app.services.worker import InvestigationWorker


class ControlledFailureService:
    """Exercise the real worker error paths without making a paid provider call."""

    def __init__(
        self,
        investigations: SupabaseInvestigationRepository,
        error: RetryableInvestigationError | PermanentInvestigationError,
    ) -> None:
        self._investigations = investigations
        self._error = error

    async def execute(
        self,
        _investigation_id: UUID,
        _job_id: UUID | None = None,
        _queued_at: datetime | None = None,
    ) -> NoReturn:
        raise self._error

    async def mark_retry_scheduled(self, investigation_id: UUID) -> object:
        return await self._investigations.update_progress(
            investigation_id,
            InvestigationStatus.PENDING,
            InvestigationStage.RETRY_SCHEDULED,
        )

    async def mark_failed(self, investigation_id: UUID, error_message: str) -> object:
        return await self._investigations.fail(investigation_id, error_message)


async def create_verification_incident(
    incidents: IncidentService,
    repository_full_name: str,
    title: str,
    description: str,
) -> UUID:
    incident = await incidents.create(
        IncidentCreate(
            title=title,
            description=description,
            severity=Severity.HIGH,
            started_at=datetime.now(UTC),
            repository_full_name=repository_full_name,
        )
    )
    return incident.id


async def fetch_one(
    storage: SupabaseRestClient,
    table: str,
    record_id: UUID,
) -> dict[str, object]:
    records = await storage.request(
        "GET",
        f"/{table}",
        params={"select": "*", "id": f"eq.{record_id}", "limit": "1"},
    )
    if len(records) != 1:
        raise RuntimeError(f"Expected one {table} record for {record_id}")
    return records[0]


async def verify_queue(repository_full_name: str) -> dict[str, object]:
    settings = Settings()
    supabase_url, supabase_key = settings.require_supabase()
    storage = SupabaseRestClient(supabase_url, supabase_key)
    incident_service = IncidentService(SupabaseIncidentRepository(storage))
    investigations = SupabaseInvestigationRepository(storage)
    jobs = SupabaseInvestigationJobRepository(storage)

    active = await storage.request(
        "GET",
        "/investigation_jobs",
        params={
            "select": "id,status,investigation_id",
            "status": "in.(queued,running,retry_scheduled)",
        },
    )
    if active:
        raise RuntimeError(
            "Live contention verification requires an idle queue; active jobs were found"
        )

    contention_incident_id = await create_verification_incident(
        incident_service,
        repository_full_name,
        "[Day 4 verification] Atomic queue claim",
        "Controlled live verification of idempotent enqueue, concurrent claim, and stale lease.",
    )
    first_enqueue = await jobs.enqueue(contention_incident_id, "verification_v1", "none", 3)
    second_enqueue = await jobs.enqueue(contention_incident_id, "verification_v1", "none", 3)
    if first_enqueue.investigation_id != second_enqueue.investigation_id:
        raise RuntimeError("Duplicate enqueue created multiple active investigations")
    if not second_enqueue.already_active:
        raise RuntimeError("Duplicate enqueue was not reported as idempotent")

    first_claim, second_claim = await asyncio.gather(jobs.claim(60), jobs.claim(60))
    claims = [claim for claim in (first_claim, second_claim) if claim is not None]
    if len(claims) != 1:
        raise RuntimeError(f"Concurrent workers claimed {len(claims)} jobs instead of one")
    claim = claims[0]
    if claim.investigation_id != first_enqueue.investigation_id:
        raise RuntimeError("Worker claimed an unexpected investigation")

    expired_at = datetime.now(UTC) - timedelta(seconds=5)
    await storage.request(
        "PATCH",
        "/investigation_jobs",
        params={"select": "id", "id": f"eq.{claim.id}"},
        json_body={"lease_expires_at": expired_at.isoformat()},
        prefer_representation=True,
    )
    reclaimed = await jobs.claim(60)
    if reclaimed is None or reclaimed.id != claim.id:
        raise RuntimeError("Expired lease was not reclaimed")
    if not reclaimed.reclaimed_stale_lease or reclaimed.attempt_count != 2:
        raise RuntimeError("Stale lease recovery metadata is incorrect")
    await jobs.fail(reclaimed.id, "Controlled stale-lease verification complete")
    await investigations.fail(
        reclaimed.investigation_id,
        "Controlled stale-lease verification complete",
    )

    retry_incident_id = await create_verification_incident(
        incident_service,
        repository_full_name,
        "[Day 4 verification] Retry exhaustion",
        "Controlled live verification of retry classification, backoff, and exhaustion.",
    )
    retry_enqueue = await jobs.enqueue(retry_incident_id, "verification_v1", "none", 2)
    retry_worker = InvestigationWorker(
        jobs,
        ControlledFailureService(
            investigations,
            RetryableInvestigationError("Controlled provider timeout"),
        ),
        lease_seconds=60,
        poll_seconds=0.1,
        retry_base_seconds=1,
    )
    if not await retry_worker.run_once():
        raise RuntimeError("Retry verification worker did not claim a job")
    retry_job_records = await storage.request(
        "GET",
        "/investigation_jobs",
        params={
            "select": "*",
            "investigation_id": f"eq.{retry_enqueue.investigation_id}",
            "limit": "1",
        },
    )
    if len(retry_job_records) != 1:
        raise RuntimeError("Retry verification job was not persisted")
    retry_job = retry_job_records[0]
    if retry_job.get("status") != "retry_scheduled" or retry_job.get("attempt_count") != 1:
        raise RuntimeError("Retryable failure did not persist retry_scheduled state")
    next_attempt_at = datetime.fromisoformat(
        str(retry_job["next_attempt_at"]).replace("Z", "+00:00")
    )
    if next_attempt_at <= datetime.now(UTC):
        raise RuntimeError("Retry did not receive a future backoff timestamp")
    retry_job_id = UUID(str(retry_job["id"]))
    await storage.request(
        "PATCH",
        "/investigation_jobs",
        params={"select": "id", "id": f"eq.{retry_job_id}"},
        json_body={"next_attempt_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()},
        prefer_representation=True,
    )
    if not await retry_worker.run_once():
        raise RuntimeError("Exhaustion verification worker did not reclaim the retry")
    exhausted_job = await fetch_one(storage, "investigation_jobs", retry_job_id)
    if exhausted_job.get("status") != "failed" or exhausted_job.get("attempt_count") != 2:
        raise RuntimeError("Retry exhaustion did not persist a terminal failure")

    permanent_incident_id = await create_verification_incident(
        incident_service,
        repository_full_name,
        "[Day 4 verification] Permanent failure",
        "Controlled live verification that permanent errors are never retried.",
    )
    permanent_enqueue = await jobs.enqueue(permanent_incident_id, "verification_v1", "none", 3)
    permanent_worker = InvestigationWorker(
        jobs,
        ControlledFailureService(
            investigations,
            PermanentInvestigationError("Controlled invalid tool request"),
        ),
        lease_seconds=60,
        poll_seconds=0.1,
        retry_base_seconds=1,
    )
    if not await permanent_worker.run_once():
        raise RuntimeError("Permanent-failure verification worker did not claim a job")
    permanent_job_records = await storage.request(
        "GET",
        "/investigation_jobs",
        params={
            "select": "*",
            "investigation_id": f"eq.{permanent_enqueue.investigation_id}",
            "limit": "1",
        },
    )
    permanent_job = permanent_job_records[0]
    if permanent_job.get("status") != "failed" or permanent_job.get("attempt_count") != 1:
        raise RuntimeError("Permanent failure was retried or did not become terminal")

    return {
        "verified_at": datetime.now(UTC).isoformat(),
        "repository": repository_full_name,
        "idempotent_enqueue": True,
        "concurrent_claim_count": len(claims),
        "stale_lease_reclaimed": True,
        "stale_lease_attempt_count": reclaimed.attempt_count,
        "retry_scheduled": True,
        "retry_backoff_seconds": 1,
        "retry_exhausted_at_attempt": exhausted_job["attempt_count"],
        "permanent_failure_attempt_count": permanent_job["attempt_count"],
        "investigation_ids": {
            "contention": str(first_enqueue.investigation_id),
            "retry": str(retry_enqueue.investigation_id),
            "permanent": str(permanent_enqueue.investigation_id),
        },
    }


async def verify_api(repository_full_name: str, api_base_url: str) -> dict[str, object]:
    async with httpx.AsyncClient(base_url=api_base_url, timeout=30.0) as client:
        health = await client.get("/health")
        health.raise_for_status()
        incident_response = await client.post(
            "/api/v1/incidents",
            json={
                "title": "[Day 4 live] Checkout failures after deployment",
                "description": (
                    "Checkout returns HTTP 500 after deployment. Inspect recent GitHub changes "
                    "and search repository knowledge for a runbook or prior incident."
                ),
                "severity": "high",
                "started_at": datetime.now(UTC).isoformat(),
                "repository_full_name": repository_full_name,
            },
        )
        incident_response.raise_for_status()
        incident = incident_response.json()

        enqueue_started = time.perf_counter()
        accepted_response = await client.post(
            f"/api/v1/incidents/{incident['id']}/investigations"
        )
        enqueue_latency_ms = round((time.perf_counter() - enqueue_started) * 1_000, 2)
        if accepted_response.status_code != 202:
            raise RuntimeError(f"Expected HTTP 202, received {accepted_response.status_code}")
        accepted = accepted_response.json()
        duplicate_response = await client.post(
            f"/api/v1/incidents/{incident['id']}/investigations"
        )
        if duplicate_response.status_code != 202:
            raise RuntimeError("Duplicate enqueue did not return HTTP 202")
        duplicate = duplicate_response.json()
        if duplicate["investigation_id"] != accepted["investigation_id"]:
            raise RuntimeError("Duplicate HTTP enqueue created a second investigation")

        investigation_id = accepted["investigation_id"]
        observed_stages: list[str] = []
        deadline = time.monotonic() + 360
        investigation: dict[str, object] = {}
        while time.monotonic() < deadline:
            response = await client.get(f"/api/v1/investigations/{investigation_id}")
            response.raise_for_status()
            investigation = response.json()
            stage = str(investigation["stage"])
            if not observed_stages or observed_stages[-1] != stage:
                observed_stages.append(stage)
            if investigation["status"] in {"completed", "failed"}:
                break
            await asyncio.sleep(1.0)
        else:
            raise RuntimeError("Live investigation did not reach a terminal state")
        if investigation["status"] != "completed":
            raise RuntimeError(f"Live investigation failed: {investigation.get('error_message')}")

        evidence_response = await client.get(f"/api/v1/incidents/{incident['id']}/evidence")
        evidence_response.raise_for_status()
        evidence = evidence_response.json()["items"]
        evidence_ids = {item["id"] for item in evidence}
        raw_cited_ids = investigation["supporting_evidence_ids"]
        if not isinstance(raw_cited_ids, list) or not all(
            isinstance(item, str) for item in raw_cited_ids
        ):
            raise RuntimeError("Investigation returned malformed evidence IDs")
        cited_ids = set(raw_cited_ids)
        if not cited_ids or not cited_ids.issubset(evidence_ids):
            raise RuntimeError("Final investigation citations do not match persisted Evidence")

        original_hypothesis = {
            field: investigation[field]
            for field in ("summary", "confidence", "suspected_change", "supporting_evidence_ids")
        }
        accepted_review = await client.post(
            f"/api/v1/investigations/{investigation_id}/review",
            json={"decision": "accepted", "note": "Controlled Day-4 acceptance review."},
        )
        accepted_review.raise_for_status()
        rejected_review = await client.post(
            f"/api/v1/investigations/{investigation_id}/review",
            json={"decision": "rejected", "note": "Controlled Day-4 rejection review."},
        )
        rejected_review.raise_for_status()
        final_response = await client.get(f"/api/v1/investigations/{investigation_id}")
        final_response.raise_for_status()
        final_investigation = final_response.json()
        final_hypothesis = {field: final_investigation[field] for field in original_hypothesis}
        if final_hypothesis != original_hypothesis:
            raise RuntimeError("Human review mutated the immutable AI hypothesis")

        return {
            "verified_at": datetime.now(UTC).isoformat(),
            "health": health.json()["status"],
            "repository": repository_full_name,
            "incident_id": incident["id"],
            "investigation_id": investigation_id,
            "enqueue_status_code": accepted_response.status_code,
            "enqueue_latency_ms": enqueue_latency_ms,
            "duplicate_enqueue_idempotent": duplicate.get("already_active") is True,
            "observed_stages": observed_stages,
            "final_status": investigation["status"],
            "duration_ms": investigation["duration_ms"],
            "tool_call_count": investigation["tool_call_count"],
            "evidence_count": len(evidence),
            "evidence_source_types": sorted({item["source_type"] for item in evidence}),
            "citation_count": len(cited_ids),
            "citations_match_persisted_evidence": True,
            "review_accept_then_reject": rejected_review.json()["decision"] == "rejected",
            "review_does_not_mutate_hypothesis": True,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--mode", choices=("queue", "api"), required=True)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.mode == "queue":
        result = asyncio.run(verify_queue(arguments.repository))
    else:
        result = asyncio.run(verify_api(arguments.repository, arguments.api_base_url))
    rendered = json.dumps(result, indent=2)
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
