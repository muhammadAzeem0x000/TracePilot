from uuid import UUID

from app.repositories.incidents import IncidentRepository
from app.schemas.incident import IncidentCreate, IncidentListResponse, IncidentResponse


class IncidentNotFoundError(Exception):
    def __init__(self, incident_id: UUID) -> None:
        super().__init__(f"Incident {incident_id} was not found")
        self.incident_id = incident_id


class IncidentService:
    def __init__(self, repository: IncidentRepository) -> None:
        self._repository = repository

    async def create(self, incident: IncidentCreate) -> IncidentResponse:
        return await self._repository.create(incident)

    async def list(self) -> IncidentListResponse:
        incidents = await self._repository.list()
        return IncidentListResponse(items=incidents, count=len(incidents))

    async def get(self, incident_id: UUID) -> IncidentResponse:
        incident = await self._repository.get(incident_id)
        if incident is None:
            raise IncidentNotFoundError(incident_id)
        return incident

