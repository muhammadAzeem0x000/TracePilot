from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

type EvidenceMetadataValue = str | int | float | bool | None


class EvidenceSourceType(StrEnum):
    GITHUB_COMMIT = "github_commit"
    GITHUB_COMMIT_SEARCH = "github_commit_search"
    GITHUB_PULL_REQUEST = "github_pull_request"
    GITHUB_PULL_REQUEST_SEARCH = "github_pull_request_search"
    GITHUB_PULL_REQUEST_FILE = "github_pull_request_file"
    KNOWLEDGE_CHUNK = "knowledge_chunk"


class EvidenceCreate(BaseModel):
    incident_id: UUID
    investigation_id: UUID
    source_type: EvidenceSourceType
    source_reference: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=50_000)
    metadata: dict[str, EvidenceMetadataValue] = Field(default_factory=dict)


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    investigation_id: UUID | None
    source_type: EvidenceSourceType
    source_reference: str | None
    content: str
    metadata: dict[str, EvidenceMetadataValue]
    collected_at: AwareDatetime


class EvidenceListResponse(BaseModel):
    items: list[EvidenceResponse]
    count: int = Field(ge=0)
