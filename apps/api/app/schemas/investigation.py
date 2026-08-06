from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class InvestigationStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class InvestigationStage(StrEnum):
    QUEUED = "queued"
    COLLECTING_EVIDENCE = "collecting_evidence"
    RETRIEVING_KNOWLEDGE = "retrieving_knowledge"
    REASONING = "reasoning"
    FINALIZING = "finalizing"
    RETRY_SCHEDULED = "retry_scheduled"
    COMPLETED = "completed"
    FAILED = "failed"


class InvestigationJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    RETRY_SCHEDULED = "retry_scheduled"
    COMPLETED = "completed"
    FAILED = "failed"


class InvestigationReviewDecision(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class InvestigationReviewCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    decision: InvestigationReviewDecision
    note: str | None = Field(default=None, min_length=1, max_length=2_000)


class InvestigationReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    investigation_id: UUID
    decision: InvestigationReviewDecision
    note: str | None
    reviewed_at: AwareDatetime
    created_at: AwareDatetime
    updated_at: AwareDatetime


class InvestigationAcceptedResponse(BaseModel):
    investigation_id: UUID
    status: InvestigationStatus
    stage: InvestigationStage
    created_at: AwareDatetime
    already_active: bool = False


class InvestigationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    investigation_id: UUID
    status: InvestigationJobStatus
    attempt_count: int = Field(ge=0)
    max_attempts: int = Field(ge=1, le=10)
    next_attempt_at: AwareDatetime
    locked_at: AwareDatetime | None
    lease_expires_at: AwareDatetime | None
    last_error: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    completed_at: AwareDatetime | None
    reclaimed_stale_lease: bool = False


class PreliminaryInvestigationResult(BaseModel):
    """The only model output that may be persisted as a completed result."""

    summary: str = Field(min_length=1, max_length=4_000)
    confidence: float = Field(ge=0.0, le=1.0)
    suspected_change: str | None = Field(max_length=2_000)
    supporting_evidence_ids: list[UUID] = Field(max_length=20)
    missing_information: list[str] = Field(max_length=20)
    recommended_next_steps: list[str] = Field(max_length=20)

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
    stage: InvestigationStage = InvestigationStage.QUEUED
    summary: str | None
    confidence: float | None
    suspected_change: str | None
    supporting_evidence_ids: list[UUID] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)
    error_message: str | None
    prompt_version: str | None
    model_name: str | None
    tool_call_count: int = Field(default=0, ge=0)
    duration_ms: int | None = Field(default=None, ge=0)
    review: InvestigationReviewResponse | None = None
    started_at: AwareDatetime
    completed_at: AwareDatetime | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class InvestigationListResponse(BaseModel):
    items: list[InvestigationResponse]
    count: int = Field(ge=0)
