from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from app.db.supabase import StorageError, SupabaseRestClient
from app.repositories.incidents import RepositoryError
from app.schemas.investigation import (
    InvestigationAcceptedResponse,
    InvestigationJobResponse,
    InvestigationJobStatus,
)


class InvestigationJobRepository(Protocol):
    async def enqueue(
        self,
        incident_id: UUID,
        prompt_version: str,
        model_name: str,
        max_attempts: int,
    ) -> InvestigationAcceptedResponse: ...

    async def claim(self, lease_seconds: int) -> InvestigationJobResponse | None: ...

    async def complete(self, job_id: UUID) -> InvestigationJobResponse: ...

    async def schedule_retry(
        self,
        job_id: UUID,
        error_message: str,
        next_attempt_at: datetime,
    ) -> InvestigationJobResponse: ...

    async def fail(self, job_id: UUID, error_message: str) -> InvestigationJobResponse: ...


class SupabaseInvestigationJobRepository:
    def __init__(self, client: SupabaseRestClient) -> None:
        self._client = client

    async def enqueue(
        self,
        incident_id: UUID,
        prompt_version: str,
        model_name: str,
        max_attempts: int,
    ) -> InvestigationAcceptedResponse:
        try:
            records = await self._client.request(
                "POST",
                "/rpc/enqueue_investigation_job",
                json_body={
                    "p_incident_id": str(incident_id),
                    "p_prompt_version": prompt_version,
                    "p_model_name": model_name,
                    "p_max_attempts": max_attempts,
                },
            )
            if len(records) != 1:
                raise RepositoryError("Investigation enqueue returned no record")
            record = records[0]
            return InvestigationAcceptedResponse.model_validate(
                {
                    "investigation_id": record.get("investigation_id"),
                    "status": record.get("investigation_status"),
                    "stage": record.get("investigation_stage"),
                    "created_at": record.get("investigation_created_at"),
                    "already_active": record.get("already_active", False),
                }
            )
        except (StorageError, ValidationError) as exc:
            raise RepositoryError("Unable to enqueue investigation") from exc

    async def claim(self, lease_seconds: int) -> InvestigationJobResponse | None:
        try:
            records = await self._client.request(
                "POST",
                "/rpc/claim_investigation_job",
                json_body={"p_lease_seconds": lease_seconds},
            )
            return InvestigationJobResponse.model_validate(records[0]) if records else None
        except (StorageError, ValidationError) as exc:
            raise RepositoryError("Unable to claim investigation job") from exc

    async def complete(self, job_id: UUID) -> InvestigationJobResponse:
        return await self._update(
            job_id,
            {
                "status": InvestigationJobStatus.COMPLETED.value,
                "completed_at": datetime.now(UTC).isoformat(),
                "locked_at": None,
                "lease_expires_at": None,
                "last_error": None,
            },
            "Unable to complete investigation job",
        )

    async def schedule_retry(
        self,
        job_id: UUID,
        error_message: str,
        next_attempt_at: datetime,
    ) -> InvestigationJobResponse:
        return await self._update(
            job_id,
            {
                "status": InvestigationJobStatus.RETRY_SCHEDULED.value,
                "next_attempt_at": next_attempt_at.isoformat(),
                "last_error": error_message[:1_000],
                "locked_at": None,
                "lease_expires_at": None,
                "completed_at": None,
            },
            "Unable to schedule investigation retry",
        )

    async def fail(self, job_id: UUID, error_message: str) -> InvestigationJobResponse:
        return await self._update(
            job_id,
            {
                "status": InvestigationJobStatus.FAILED.value,
                "last_error": error_message[:1_000],
                "completed_at": datetime.now(UTC).isoformat(),
                "locked_at": None,
                "lease_expires_at": None,
            },
            "Unable to fail investigation job",
        )

    async def _update(
        self,
        job_id: UUID,
        payload: dict[str, object],
        error_message: str,
    ) -> InvestigationJobResponse:
        try:
            records = await self._client.request(
                "PATCH",
                "/investigation_jobs",
                params={"select": "*", "id": f"eq.{job_id}"},
                json_body=payload,
                prefer_representation=True,
            )
            if len(records) != 1:
                raise RepositoryError(error_message)
            return InvestigationJobResponse.model_validate(records[0])
        except (StorageError, ValidationError) as exc:
            raise RepositoryError(error_message) from exc
