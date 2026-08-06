from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class AIOperationType(StrEnum):
    QUEUE_WAIT = "queue_wait"
    INVESTIGATION = "investigation"
    LLM_CALL = "llm_call"
    GITHUB_TOOL = "github_tool"
    EMBEDDING = "embedding"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    RERANK = "rerank"


class AIOperationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AIOperationCreate(BaseModel):
    investigation_id: UUID
    job_id: UUID | None = None
    trace_id: UUID
    span_id: UUID
    parent_span_id: UUID | None = None
    operation_type: AIOperationType
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=200)
    prompt_version: str | None = Field(default=None, max_length=100)
    tool_name: str | None = Field(default=None, max_length=100)
    started_at: datetime
    completed_at: datetime
    duration_ms: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    fallback_used: bool = False
    fallback_reason: str | None = Field(default=None, max_length=500)
    status: AIOperationStatus
    error_type: str | None = Field(default=None, max_length=200)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class AIOperationResponse(AIOperationCreate):
    id: UUID
    created_at: datetime


class LatencyMetric(BaseModel):
    operation_type: AIOperationType
    call_count: int = Field(ge=0)
    total_duration_ms: int = Field(ge=0)
    average_duration_ms: float = Field(ge=0)


class InvestigationMetricsResponse(BaseModel):
    investigation_id: UUID
    trace_ids: list[UUID]
    operations: list[AIOperationResponse]
    latency: list[LatencyMetric]
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: float | None
    cost_status: str
    fallback_used: bool
    serving_providers: list[str]
    serving_models: list[str]
