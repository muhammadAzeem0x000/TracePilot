from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.schemas.incident import RepositoryFullName

type KnowledgeMetadataValue = str | int | float | bool | None


class KnowledgeSourceType(StrEnum):
    RUNBOOK = "runbook"
    ARCHITECTURE = "architecture"
    PAST_INCIDENT = "past_incident"


class KnowledgeSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_full_name: RepositoryFullName
    source_type: KnowledgeSourceType
    title: str
    source_reference: str
    content_hash: str
    metadata: dict[str, KnowledgeMetadataValue]
    created_at: AwareDatetime
    updated_at: AwareDatetime


class KnowledgeChunk(BaseModel):
    chunk_index: int = Field(ge=0)
    content: str = Field(min_length=1, max_length=20_000)
    token_count: int = Field(gt=0)
    metadata: dict[str, KnowledgeMetadataValue] = Field(default_factory=dict)


class EmbeddedKnowledgeChunk(KnowledgeChunk):
    embedding: list[float]


class KnowledgeChunkResponse(KnowledgeChunk):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    created_at: AwareDatetime


class KnowledgeDocument(BaseModel):
    repository_full_name: RepositoryFullName
    source_type: KnowledgeSourceType
    title: str = Field(min_length=1, max_length=300)
    source_reference: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1)
    metadata: dict[str, KnowledgeMetadataValue] = Field(default_factory=dict)


class KnowledgeIngestionAction(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"


class KnowledgeIngestionResult(BaseModel):
    source_id: UUID
    source_reference: str
    action: KnowledgeIngestionAction
    chunk_count: int = Field(ge=0)
