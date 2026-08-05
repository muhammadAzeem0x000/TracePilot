from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_incident_repository
from app.main import app
from app.repositories.incidents import IncidentRepository, RepositoryError
from app.schemas.incident import IncidentCreate, IncidentResponse

VALID_INCIDENT = {
    "title": "Checkout error spike",
    "description": "Customers receive HTTP 500 during checkout.",
    "severity": "high",
    "started_at": "2026-08-04T08:30:00Z",
}


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "tracepilot-api"


def test_successful_incident_creation(client: TestClient) -> None:
    response = client.post("/api/v1/incidents", json=VALID_INCIDENT)

    assert response.status_code == 201
    payload = response.json()
    assert payload["title"] == VALID_INCIDENT["title"]
    assert payload["severity"] == "high"
    assert payload["status"] == "open"
    assert payload["id"]


@pytest.mark.parametrize(
    ("field", "value"),
    [("severity", "catastrophic"), ("status", "closed"), ("title", "")],
)
def test_invalid_incident_validation(
    client: TestClient,
    field: str,
    value: str,
) -> None:
    request_body = {**VALID_INCIDENT, field: value}

    response = client.post("/api/v1/incidents", json=request_body)

    assert response.status_code == 422
    assert response.json()["detail"]


def test_incident_listing(client: TestClient) -> None:
    created = client.post("/api/v1/incidents", json=VALID_INCIDENT).json()

    response = client.get("/api/v1/incidents")

    assert response.status_code == 200
    assert response.json() == {"items": [created], "count": 1}


def test_incident_retrieval(client: TestClient) -> None:
    created = client.post("/api/v1/incidents", json=VALID_INCIDENT).json()

    response = client.get(f"/api/v1/incidents/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_nonexistent_incident_returns_404(client: TestClient) -> None:
    incident_id = uuid4()

    response = client.get(f"/api/v1/incidents/{incident_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": f"Incident {incident_id} was not found"}


class FailingIncidentRepository:
    async def create(self, _incident: IncidentCreate) -> IncidentResponse:
        raise RepositoryError("database unavailable")

    async def list(self) -> list[IncidentResponse]:
        raise RepositoryError("database unavailable")

    async def get(self, _incident_id: object) -> IncidentResponse | None:
        raise RepositoryError("database unavailable")


def test_database_failure_returns_503() -> None:
    repository = FailingIncidentRepository()

    def override_repository() -> IncidentRepository:
        return repository

    app.dependency_overrides[get_incident_repository] = override_repository
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post("/api/v1/incidents", json=VALID_INCIDENT)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "Incident storage is temporarily unavailable"}

