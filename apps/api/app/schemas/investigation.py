from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class InvestigationStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class PreliminaryInvestigationResult(BaseModel):
    """The only model output that may be persisted as a completed result."""

    summary: str = Field(min_length=1, max_length=4_000)
    confidence: float = Field(ge=0.0, le=1.0)
    suspected_change: str | None = Field(default=None, max_length=2_000)
    supporting_evidence_ids: list[UUID] = Field(default_factory=list, max_length=20)
    missing_information: list[str] = Field(default_factory=list, max_length=20)
    recommended_next_steps: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("supporting_evidence_ids")
    @classmethod
    def require_unique_evidence_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("supporting evidence IDs must be unique")
        return value

    @field_validator("missing_information", "recommended_next_steps")
    @classmethod
    def validate_bounded_text_items(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item or len(item) > 1_000 for item in cleaned):
            raise ValueError("items must contain between 1 and 1000 characters")
        return cleaned

    @model_validator(mode="after")
    def reject_unsupported_high_confidence(self) -> "PreliminaryInvestigationResult":
        if self.confidence > 0.7 and not self.supporting_evidence_ids:
            raise ValueError("confidence above 0.7 requires supporting evidence")
        return self


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    status: InvestigationStatus
    summary: str | None
    confidence: float | None
    suspected_change: str | None
    supporting_evidence_ids: list[UUID] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    error_message: str | None
    prompt_version: str | None
    model_name: str | None
    started_at: AwareDatetime
    completed_at: AwareDatetime | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class InvestigationListResponse(BaseModel):
    items: list[InvestigationResponse]
    count: int = Field(ge=0)
