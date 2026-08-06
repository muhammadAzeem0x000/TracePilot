import time
from datetime import UTC, datetime
from statistics import fmean
from uuid import UUID, uuid4

from app.ai.prompts.investigation_v2 import PROMPT_VERSION
from app.ai.provider import LLMProvider, LLMProviderError
from app.evaluation.models import (
    EvaluationFailureClass,
    IncidentEvaluationMetrics,
    IncidentEvaluationReport,
    IncidentEvaluationScenario,
    IncidentScenarioEvaluation,
)
from app.evaluation.tools import ControlledEvaluationToolExecutor
from app.repositories.evidence import EvidenceRepository
from app.repositories.incidents import IncidentRepository
from app.repositories.investigations import InvestigationRepository
from app.repositories.jobs import InvestigationJobRepository
from app.repositories.reviews import InvestigationReviewRepository
from app.schemas.evidence import EvidenceCreate, EvidenceResponse
from app.schemas.incident import IncidentCreate, IncidentResponse, IncidentStatus
from app.schemas.investigation import (
    InvestigationAcceptedResponse,
    InvestigationJobResponse,
    InvestigationResponse,
    InvestigationReviewCreate,
    InvestigationReviewResponse,
    InvestigationStage,
    InvestigationStatus,
    PreliminaryInvestigationResult,
)
from app.services.investigation_errors import (
    EvidenceReferenceValidationError,
    InvalidModelOutputError,
    ToolCallLimitError,
)
from app.services.investigations import InvestigationExecutionError, InvestigationService
from app.tools.github import MalformedToolArgumentsError, UnknownToolError

HIGH_CONFIDENCE_THRESHOLD = 0.7


class EvaluationIncidentRepository:
    def __init__(self, incident: IncidentResponse) -> None:
        self.incident = incident

    async def create(self, _incident: IncidentCreate) -> IncidentResponse:
        raise AssertionError("Evaluation incidents are fixed fixtures")

    async def list(self) -> list[IncidentResponse]:
        return [self.incident]

    async def get(self, incident_id: UUID) -> IncidentResponse | None:
        return self.incident if incident_id == self.incident.id else None


class EvaluationInvestigationRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, InvestigationResponse] = {}

    async def create(
        self,
        incident_id: UUID,
        prompt_version: str,
        model_name: str,
    ) -> InvestigationResponse:
        now = datetime.now(UTC)
        stored = InvestigationResponse(
            id=uuid4(),
            incident_id=incident_id,
            status=InvestigationStatus.PENDING,
            stage=InvestigationStage.QUEUED,
            summary=None,
            confidence=None,
            suspected_change=None,
            suspected_culprit_id=None,
            error_message=None,
            prompt_version=prompt_version,
            model_name=model_name,
            started_at=now,
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        self.items[stored.id] = stored
        return stored

    async def complete(
        self,
        investigation_id: UUID,
        result: PreliminaryInvestigationResult,
        *,
        tool_call_count: int,
        duration_ms: int,
    ) -> InvestigationResponse:
        now = datetime.now(UTC)
        stored = self.items[investigation_id].model_copy(
            update={
                **result.model_dump(),
                "status": InvestigationStatus.COMPLETED,
                "stage": InvestigationStage.COMPLETED,
                "tool_call_count": tool_call_count,
                "duration_ms": duration_ms,
                "completed_at": now,
                "updated_at": now,
            }
        )
        self.items[investigation_id] = stored
        return stored

    async def fail(self, investigation_id: UUID, error_message: str) -> InvestigationResponse:
        now = datetime.now(UTC)
        stored = self.items[investigation_id].model_copy(
            update={
                "status": InvestigationStatus.FAILED,
                "stage": InvestigationStage.FAILED,
                "error_message": error_message,
                "completed_at": now,
                "updated_at": now,
            }
        )
        self.items[investigation_id] = stored
        return stored

    async def update_progress(
        self,
        investigation_id: UUID,
        status: InvestigationStatus,
        stage: InvestigationStage,
    ) -> InvestigationResponse:
        stored = self.items[investigation_id].model_copy(
            update={"status": status, "stage": stage, "updated_at": datetime.now(UTC)}
        )
        self.items[investigation_id] = stored
        return stored

    async def get(self, investigation_id: UUID) -> InvestigationResponse | None:
        return self.items.get(investigation_id)

    async def list_for_incident(self, incident_id: UUID) -> list[InvestigationResponse]:
        return [item for item in self.items.values() if item.incident_id == incident_id]


class EvaluationEvidenceRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, EvidenceResponse] = {}

    async def create(self, evidence: EvidenceCreate) -> EvidenceResponse:
        stored = EvidenceResponse(
            id=uuid4(),
            **evidence.model_dump(),
            collected_at=datetime.now(UTC),
        )
        self.items[stored.id] = stored
        return stored

    async def list_for_incident(self, incident_id: UUID) -> list[EvidenceResponse]:
        return [item for item in self.items.values() if item.incident_id == incident_id]

    async def list_for_investigation(self, investigation_id: UUID) -> list[EvidenceResponse]:
        return [item for item in self.items.values() if item.investigation_id == investigation_id]

    async def ids_for_context(
        self,
        incident_id: UUID,
        investigation_id: UUID,
        evidence_ids: set[UUID],
    ) -> set[UUID]:
        return {
            evidence_id
            for evidence_id in evidence_ids
            if (item := self.items.get(evidence_id)) is not None
            and item.incident_id == incident_id
            and item.investigation_id == investigation_id
        }


class EvaluationJobRepository:
    def __init__(self, investigations: EvaluationInvestigationRepository) -> None:
        self._investigations = investigations

    async def enqueue(
        self,
        incident_id: UUID,
        prompt_version: str,
        model_name: str,
        _max_attempts: int,
    ) -> InvestigationAcceptedResponse:
        investigation = await self._investigations.create(
            incident_id,
            prompt_version,
            model_name,
        )
        return InvestigationAcceptedResponse(
            investigation_id=investigation.id,
            status=investigation.status,
            stage=investigation.stage,
            created_at=investigation.created_at,
        )

    async def claim(self, _lease_seconds: int) -> InvestigationJobResponse | None:
        raise AssertionError("Evaluation runs inline and never claim queue jobs")

    async def complete(self, _job_id: UUID) -> InvestigationJobResponse:
        raise AssertionError("Evaluation runs inline and never mutate queue jobs")

    async def schedule_retry(
        self,
        _job_id: UUID,
        _error_message: str,
        _next_attempt_at: datetime,
    ) -> InvestigationJobResponse:
        raise AssertionError("Evaluation runs inline and never schedule queue retries")

    async def fail(self, _job_id: UUID, _error_message: str) -> InvestigationJobResponse:
        raise AssertionError("Evaluation runs inline and never mutate queue jobs")


class EvaluationReviewRepository:
    async def upsert(
        self,
        _investigation_id: UUID,
        _review: InvestigationReviewCreate,
    ) -> InvestigationReviewResponse:
        raise AssertionError("Human review is outside automated evaluation")

    async def get(self, _investigation_id: UUID) -> InvestigationReviewResponse | None:
        return None


async def evaluate_incidents(
    scenarios: list[IncidentEvaluationScenario],
    llm: LLMProvider,
) -> IncidentEvaluationReport:
    if not scenarios:
        raise ValueError("Incident evaluation requires at least one scenario")
    results = [await _evaluate_scenario(scenario, llm) for scenario in scenarios]
    return IncidentEvaluationReport(
        prompt_version=PROMPT_VERSION,
        model_name=llm.model_name,
        high_confidence_threshold=HIGH_CONFIDENCE_THRESHOLD,
        metrics=_aggregate(results),
        scenarios=results,
    )


async def _evaluate_scenario(
    scenario: IncidentEvaluationScenario,
    llm: LLMProvider,
) -> IncidentScenarioEvaluation:
    now = datetime.now(UTC)
    incident = IncidentResponse(
        id=uuid4(),
        title=scenario.incident.title,
        description=scenario.incident.description,
        severity=scenario.incident.severity,
        status=IncidentStatus.OPEN,
        started_at=scenario.incident.started_at,
        repository_full_name=scenario.incident.repository_full_name,
        created_at=now,
        updated_at=now,
    )
    incidents: IncidentRepository = EvaluationIncidentRepository(incident)
    investigation_store = EvaluationInvestigationRepository()
    investigations: InvestigationRepository = investigation_store
    evidence_store = EvaluationEvidenceRepository()
    evidence: EvidenceRepository = evidence_store
    jobs: InvestigationJobRepository = EvaluationJobRepository(investigation_store)
    reviews: InvestigationReviewRepository = EvaluationReviewRepository()
    tools = ControlledEvaluationToolExecutor(scenario, evidence)
    service = InvestigationService(
        incidents,
        investigations,
        evidence,
        jobs,
        reviews,
        tools,
        llm,
    )

    started = time.perf_counter()
    completed: InvestigationResponse | None = None
    caught: InvestigationExecutionError | None = None
    try:
        completed = await service.run(incident.id)
    except InvestigationExecutionError as exc:
        caught = exc
    latency_ms = (time.perf_counter() - started) * 1_000

    cited_source_references: list[str] = []
    if completed is not None:
        cited_source_references = [
            item.source_reference or ""
            for evidence_id in completed.supporting_evidence_ids
            if (item := evidence_store.items.get(evidence_id)) is not None
        ]
    relevant = set(scenario.relevant_evidence_source_references)
    cited = set(cited_source_references)
    precision = len(cited & relevant) / len(cited) if cited else 0.0
    recall = len(cited & relevant) / len(relevant)
    predicted = completed.suspected_culprit_id if completed else None
    acceptable = {scenario.expected_culprit_id, *scenario.acceptable_culprit_ids}
    correct = predicted in acceptable
    invalid_citation = _caused_by(caught, EvidenceReferenceValidationError)
    failure_class, failure_reason = _classify_result(
        scenario,
        tools.calls,
        completed,
        caught,
        correct,
        recall,
    )
    return IncidentScenarioEvaluation(
        scenario_id=scenario.id,
        completed=completed is not None,
        expected_culprit_id=scenario.expected_culprit_id,
        predicted_culprit_id=predicted,
        culprit_correct=correct,
        cited_source_references=cited_source_references,
        citation_precision=precision,
        citation_recall=recall,
        invalid_citation=invalid_citation,
        confidence=completed.confidence if completed else None,
        tool_calls=len(tools.calls),
        called_tools=tools.calls,
        latency_ms=latency_ms,
        failure_class=failure_class,
        failure_reason=failure_reason,
    )


def _classify_result(
    scenario: IncidentEvaluationScenario,
    called_tools: list[str],
    completed: InvestigationResponse | None,
    error: InvestigationExecutionError | None,
    culprit_correct: bool,
    citation_recall: float,
) -> tuple[EvaluationFailureClass | None, str | None]:
    if error is not None:
        if _caused_by(error, EvidenceReferenceValidationError):
            return EvaluationFailureClass.CITATION, str(error)
        if _caused_by(error, LLMProviderError):
            return EvaluationFailureClass.PROVIDER, str(error)
        if _caused_by(error, InvalidModelOutputError):
            return EvaluationFailureClass.STRUCTURED_OUTPUT, str(error)
        if _caused_by(error, (UnknownToolError, MalformedToolArgumentsError, ToolCallLimitError)):
            return EvaluationFailureClass.TOOL_SELECTION, str(error)
        return EvaluationFailureClass.OTHER, str(error)
    if completed is None:
        return EvaluationFailureClass.OTHER, "Investigation produced no terminal result"
    if culprit_correct and citation_recall >= 1.0:
        return None, None
    expected_tools = {
        fixture.tool_name
        for fixture in scenario.evidence
        if fixture.source_reference == scenario.expected_culprit_id
    }
    if expected_tools.isdisjoint(called_tools):
        return (
            EvaluationFailureClass.TOOL_SELECTION,
            "The model did not call a tool capable of returning the expected culprit.",
        )
    if citation_recall < 1.0 and culprit_correct:
        return (
            EvaluationFailureClass.EVIDENCE_SELECTION,
            "The diagnosis was correct but did not cite all relevant evidence.",
        )
    return (
        EvaluationFailureClass.REASONING,
        "Retrieved evidence did not lead to the expected culprit.",
    )


def _caused_by(
    error: BaseException | None,
    expected: type[BaseException] | tuple[type[BaseException], ...],
) -> bool:
    current = error
    while current is not None:
        if isinstance(current, expected):
            return True
        current = current.__cause__ or current.__context__
    return False


def _aggregate(results: list[IncidentScenarioEvaluation]) -> IncidentEvaluationMetrics:
    count = len(results)
    completed = [item for item in results if item.completed]
    correct = [item for item in results if item.culprit_correct]
    incorrect = [item for item in completed if not item.culprit_correct]
    confidences = [item.confidence for item in completed if item.confidence is not None]
    correct_confidences = [item.confidence for item in correct if item.confidence is not None]
    incorrect_confidences = [item.confidence for item in incorrect if item.confidence is not None]
    return IncidentEvaluationMetrics(
        scenario_count=count,
        completed_count=len(completed),
        failed_count=count - len(completed),
        completion_rate=len(completed) / count,
        culprit_accuracy=len(correct) / count,
        citation_precision=fmean(item.citation_precision for item in results),
        citation_recall=fmean(item.citation_recall for item in results),
        invalid_citation_rate=sum(item.invalid_citation for item in results) / count,
        average_tool_calls=fmean(item.tool_calls for item in results),
        average_latency_ms=fmean(item.latency_ms for item in results),
        average_confidence=fmean(confidences) if confidences else None,
        average_confidence_correct=(
            fmean(correct_confidences) if correct_confidences else None
        ),
        average_confidence_incorrect=(
            fmean(incorrect_confidences) if incorrect_confidences else None
        ),
        high_confidence_incorrect_count=sum(
            item.confidence is not None
            and item.confidence >= HIGH_CONFIDENCE_THRESHOLD
            and not item.culprit_correct
            for item in results
        ),
    )
