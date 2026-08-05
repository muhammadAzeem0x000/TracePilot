from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_incident_repository
from app.main import app
from app.repositories.incidents import IncidentRepository
from app.schemas.incident import IncidentCreate, IncidentResponse


class FakeIncidentRepository:
    def __init__(self) -> None:
        self.incidents: dict[UUID, IncidentResponse] = {}

    async def create(self, incident: IncidentCreate) -> IncidentResponse:
        now = datetime.now(UTC)
        stored = IncidentResponse(
            id=uuid4(),
            title=incident.title,
            description=incident.description,
            severity=incident.severity,
            status=incident.status,
            started_at=incident.started_at,
            created_at=now,
            updated_at=now,
        )
        self.incidents[stored.id] = stored
        return stored

    async def list(self) -> list[IncidentResponse]:
        return sorted(self.incidents.values(), key=lambda item: item.created_at, reverse=True)

    async def get(self, incident_id: UUID) -> IncidentResponse | None:
        return self.incidents.get(incident_id)


@pytest.fixture
def repository() -> FakeIncidentRepository:
    return FakeIncidentRepository()


@pytest.fixture
def client(repository: FakeIncidentRepository) -> Iterator[TestClient]:
    def override_repository() -> IncidentRepository:
        return repository

    app.dependency_overrides[get_incident_repository] = override_repository
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

