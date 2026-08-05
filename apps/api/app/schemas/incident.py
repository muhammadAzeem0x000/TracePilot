from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"


class IncidentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    severity: Severity
    status: IncidentStatus = IncidentStatus.OPEN
    started_at: AwareDatetime


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    severity: Severity
    status: IncidentStatus
    started_at: AwareDatetime
    created_at: AwareDatetime
    updated_at: AwareDatetime


class IncidentListResponse(BaseModel):
    items: list[IncidentResponse]
    count: int = Field(ge=0)


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    detail: str

