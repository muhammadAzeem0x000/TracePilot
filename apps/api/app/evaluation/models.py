from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.schemas.evidence import EvidenceMetadataValue, EvidenceSourceType
from app.schemas.incident import RepositoryFullName, Severity


class EvaluationFailureClass(StrEnum):
    TOOL_SELECTION = "tool_selection_failure"
    EVIDENCE_SELECTION = "retrieval/evidence_selection_failure"
    REASONING = "reasoning_failure"
    STRUCTURED_OUTPUT = "structured_output_failure"
    PROVIDER = "provider_failure"
    CITATION = "citation_failure"
    OTHER = "other"


class EvaluationIncidentInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    severity: Severity
    started_at: AwareDatetime
    repository_full_name: RepositoryFullName


class EvaluationEvidenceFixture(BaseModel):
    tool_name: str = Field(min_length=1, max_length=64)
    source_type: EvidenceSourceType
    source_reference: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=50_000)
    metadata: dict[str, EvidenceMetadataValue] = Field(default_factory=dict)


class IncidentEvaluationScenario(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,80}$")
    incident: EvaluationIncidentInput
    evidence: list[EvaluationEvidenceFixture] = Field(min_length=2)
    expected_culprit_id: str = Field(min_length=1, max_length=500)
    acceptable_culprit_ids: list[str] = Field(default_factory=list)
    relevant_evidence_source_references: list[str] = Field(min_length=1)
    ground_truth: str = Field(min_length=1, max_length=2_000)


class IncidentScenarioEvaluation(BaseModel):
    scenario_id: str
    completed: bool
    expected_culprit_id: str
    predicted_culprit_id: str | None
    culprit_correct: bool
    cited_source_references: list[str]
    citation_precision: float = Field(ge=0.0, le=1.0)
    citation_recall: float = Field(ge=0.0, le=1.0)
    invalid_citation: bool
    confidence: float | None
    tool_calls: int = Field(ge=0)
    called_tools: list[str]
    latency_ms: float = Field(ge=0.0)
    serving_provider: str | None = None
    serving_model: str | None = None
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    fallback_used: bool = False
    fallback_reasons: list[str] = Field(default_factory=list)
    failure_class: EvaluationFailureClass | None
    failure_reason: str | None


class IncidentEvaluationMetrics(BaseModel):
    scenario_count: int = Field(gt=0)
    completed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    completion_rate: float = Field(ge=0.0, le=1.0)
    culprit_accuracy: float = Field(ge=0.0, le=1.0)
    citation_precision: float = Field(ge=0.0, le=1.0)
    citation_recall: float = Field(ge=0.0, le=1.0)
    invalid_citation_rate: float = Field(ge=0.0, le=1.0)
    average_tool_calls: float = Field(ge=0.0)
    average_latency_ms: float = Field(ge=0.0)
    average_confidence: float | None
    average_confidence_correct: float | None
    average_confidence_incorrect: float | None
    high_confidence_incorrect_count: int = Field(ge=0)
    average_input_tokens: float | None = None
    average_output_tokens: float | None = None
    average_total_tokens: float | None = None
    average_estimated_cost_usd: float | None = None
    fallback_scenario_count: int = Field(default=0, ge=0)


class IncidentEvaluationReport(BaseModel):
    prompt_version: str
    model_name: str
    high_confidence_threshold: float
    metrics: IncidentEvaluationMetrics
    scenarios: list[IncidentScenarioEvaluation]
