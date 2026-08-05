from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from app.db.supabase import StorageError, SupabaseRestClient
from app.schemas.incident import IncidentCreate, IncidentResponse


class RepositoryError(Exception):
    """Stable application error for persistence failures."""


class IncidentRepository(Protocol):
    async def create(self, incident: IncidentCreate) -> IncidentResponse: ...

    async def list(self) -> list[IncidentResponse]: ...

    async def get(self, incident_id: UUID) -> IncidentResponse | None: ...


class SupabaseIncidentRepository:
    def __init__(self, client: SupabaseRestClient) -> None:
        self._client = client

    async def create(self, incident: IncidentCreate) -> IncidentResponse:
        payload: dict[str, object] = {
            "title": incident.title,
            "description": incident.description,
            "severity": incident.severity.value,
            "status": incident.status.value,
            "started_at": incident.started_at.isoformat(),
        }
        try:
            records = await self._client.request(
                "POST",
                "/incidents",
                params={"select": "*"},
                json_body=payload,
                prefer_representation=True,
            )
            if len(records) != 1:
                raise RepositoryError("Incident insert returned no record")
            return IncidentResponse.model_validate(records[0])
        except (StorageError, ValidationError) as exc:
            raise RepositoryError("Unable to create incident") from exc

    async def list(self) -> list[IncidentResponse]:
        try:
            records = await self._client.request(
                "GET",
                "/incidents",
                params={"select": "*", "order": "created_at.desc"},
            )
            return [IncidentResponse.model_validate(record) for record in records]
        except (StorageError, ValidationError) as exc:
            raise RepositoryError("Unable to list incidents") from exc

    async def get(self, incident_id: UUID) -> IncidentResponse | None:
        try:
            records = await self._client.request(
                "GET",
                "/incidents",
                params={"select": "*", "id": f"eq.{incident_id}", "limit": "1"},
            )
            if not records:
                return None
            return IncidentResponse.model_validate(records[0])
        except (StorageError, ValidationError) as exc:
            raise RepositoryError("Unable to retrieve incident") from exc
