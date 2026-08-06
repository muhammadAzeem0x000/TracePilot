from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from app.db.supabase import StorageError, SupabaseRestClient
from app.repositories.incidents import RepositoryError
from app.schemas.evidence import EvidenceCreate, EvidenceResponse


class EvidenceRepository(Protocol):
    async def create(self, evidence: EvidenceCreate) -> EvidenceResponse: ...

    async def list_for_incident(self, incident_id: UUID) -> list[EvidenceResponse]: ...

    async def list_for_investigation(self, investigation_id: UUID) -> list[EvidenceResponse]: ...

    async def ids_for_context(
        self,
        incident_id: UUID,
        investigation_id: UUID,
        evidence_ids: set[UUID],
    ) -> set[UUID]: ...


class SupabaseEvidenceRepository:
    def __init__(self, client: SupabaseRestClient) -> None:
        self._client = client

    async def create(self, evidence: EvidenceCreate) -> EvidenceResponse:
        payload: dict[str, object] = {
            "incident_id": str(evidence.incident_id),
            "investigation_id": str(evidence.investigation_id),
            "source_type": evidence.source_type.value,
            "source_reference": evidence.source_reference,
            "content": evidence.content,
            "metadata": evidence.metadata,
        }
        try:
            records = await self._client.request(
                "POST",
                "/evidence",
                params={"select": "*"},
                json_body=payload,
                prefer_representation=True,
            )
            if len(records) != 1:
                raise RepositoryError("Evidence insert returned no record")
            return EvidenceResponse.model_validate(records[0])
        except (StorageError, ValidationError) as exc:
            raise RepositoryError("Unable to create evidence") from exc

    async def list_for_incident(self, incident_id: UUID) -> list[EvidenceResponse]:
        return await self._list({"incident_id": f"eq.{incident_id}"})

    async def list_for_investigation(self, investigation_id: UUID) -> list[EvidenceResponse]:
        return await self._list({"investigation_id": f"eq.{investigation_id}"})

    async def ids_for_context(
        self,
        incident_id: UUID,
        investigation_id: UUID,
        evidence_ids: set[UUID],
    ) -> set[UUID]:
        if not evidence_ids:
            return set()
        id_filter = ",".join(str(item) for item in evidence_ids)
        try:
            records = await self._client.request(
                "GET",
                "/evidence",
                params={
                    "select": "id",
                    "id": f"in.({id_filter})",
                    "incident_id": f"eq.{incident_id}",
                    "investigation_id": f"eq.{investigation_id}",
                },
            )
            return {UUID(str(record["id"])) for record in records if "id" in record}
        except (StorageError, ValueError) as exc:
            raise RepositoryError("Unable to validate evidence references") from exc

    async def _list(self, filters: dict[str, str]) -> list[EvidenceResponse]:
        params = {"select": "*", "order": "collected_at.asc", **filters}
        try:
            records = await self._client.request("GET", "/evidence", params=params)
            return [EvidenceResponse.model_validate(record) for record in records]
        except (StorageError, ValidationError) as exc:
            raise RepositoryError("Unable to list evidence") from exc
