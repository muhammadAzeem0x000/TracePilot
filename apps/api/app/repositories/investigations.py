from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from app.db.supabase import StorageError, SupabaseRestClient
from app.repositories.incidents import RepositoryError
from app.schemas.investigation import (
    InvestigationResponse,
    InvestigationStage,
    InvestigationStatus,
    PreliminaryInvestigationResult,
)


class InvestigationRepository(Protocol):
    async def create(
        self,
        incident_id: UUID,
        prompt_version: str,
        model_name: str,
    ) -> InvestigationResponse: ...

    async def complete(
        self,
        investigation_id: UUID,
        result: PreliminaryInvestigationResult,
        *,
        tool_call_count: int,
        duration_ms: int,
    ) -> InvestigationResponse: ...

    async def fail(self, investigation_id: UUID, error_message: str) -> InvestigationResponse: ...

    async def update_progress(
        self,
        investigation_id: UUID,
        status: InvestigationStatus,
        stage: InvestigationStage,
    ) -> InvestigationResponse: ...

    async def get(self, investigation_id: UUID) -> InvestigationResponse | None: ...

    async def list_for_incident(self, incident_id: UUID) -> list[InvestigationResponse]: ...


class SupabaseInvestigationRepository:
    def __init__(self, client: SupabaseRestClient) -> None:
        self._client = client

    async def create(
        self,
        incident_id: UUID,
        prompt_version: str,
        model_name: str,
    ) -> InvestigationResponse:
        return await self._write(
            "POST",
            "/investigations",
            {
                "incident_id": str(incident_id),
                "status": "pending",
                "stage": "queued",
                "started_at": datetime.now(UTC).isoformat(),
                "prompt_version": prompt_version,
                "model_name": model_name,
            },
            "Unable to create investigation",
        )

    async def complete(
        self,
        investigation_id: UUID,
        result: PreliminaryInvestigationResult,
        *,
        tool_call_count: int,
        duration_ms: int,
    ) -> InvestigationResponse:
        return await self._write(
            "PATCH",
            "/investigations",
            {
                "status": "completed",
                "stage": "completed",
                "summary": result.summary,
                "confidence": result.confidence,
                "suspected_change": result.suspected_change,
                "suspected_culprit_id": result.suspected_culprit_id,
                "supporting_evidence_ids": [str(item) for item in result.supporting_evidence_ids],
                "missing_information": result.missing_information,
                "recommended_next_steps": result.recommended_next_steps,
                "error_message": None,
                "tool_call_count": tool_call_count,
                "duration_ms": duration_ms,
            },
            "Unable to complete investigation",
            investigation_id,
        )

    async def fail(self, investigation_id: UUID, error_message: str) -> InvestigationResponse:
        return await self._write(
            "PATCH",
            "/investigations",
            {
                "status": "failed",
                "stage": "failed",
                "error_message": error_message[:1_000],
            },
            "Unable to mark investigation failed",
            investigation_id,
        )

    async def update_progress(
        self,
        investigation_id: UUID,
        status: InvestigationStatus,
        stage: InvestigationStage,
    ) -> InvestigationResponse:
        return await self._write(
            "PATCH",
            "/investigations",
            {"status": status.value, "stage": stage.value, "error_message": None},
            "Unable to update investigation progress",
            investigation_id,
        )

    async def get(self, investigation_id: UUID) -> InvestigationResponse | None:
        items = await self._read(
            {"select": "*", "id": f"eq.{investigation_id}", "limit": "1"},
            "Unable to retrieve investigation",
        )
        return items[0] if items else None

    async def list_for_incident(self, incident_id: UUID) -> list[InvestigationResponse]:
        return await self._read(
            {
                "select": "*",
                "incident_id": f"eq.{incident_id}",
                "order": "created_at.desc",
            },
            "Unable to list investigations",
        )

    async def _write(
        self,
        method: str,
        path: str,
        payload: dict[str, object],
        error_message: str,
        investigation_id: UUID | None = None,
    ) -> InvestigationResponse:
        params = {"select": "*"}
        if investigation_id is not None:
            params["id"] = f"eq.{investigation_id}"
        try:
            records = await self._client.request(
                method,
                path,
                params=params,
                json_body=payload,
                prefer_representation=True,
            )
            if len(records) != 1:
                raise RepositoryError(error_message)
            return InvestigationResponse.model_validate(records[0])
        except (StorageError, ValidationError) as exc:
            raise RepositoryError(error_message) from exc

    async def _read(
        self,
        params: dict[str, str],
        error_message: str,
    ) -> list[InvestigationResponse]:
        try:
            records = await self._client.request("GET", "/investigations", params=params)
            return [InvestigationResponse.model_validate(record) for record in records]
        except (StorageError, ValidationError) as exc:
            raise RepositoryError(error_message) from exc
