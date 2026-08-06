import asyncio
import json
import time
from collections.abc import Awaitable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai.provider import LLMUnavailableError
from app.ai.tool_definitions import GITHUB_TOOL_DEFINITIONS
from app.api.dependencies import get_investigation_service
from app.integrations.github import GitHubNotFoundError
from app.repositories.evidence import EvidenceRepository
from app.repositories.incidents import IncidentRepository
from app.repositories.investigations import InvestigationRepository
from app.repositories.jobs import InvestigationJobRepository
from app.repositories.reviews import InvestigationReviewRepository
from app.schemas.evidence import EvidenceCreate, EvidenceResponse, EvidenceSourceType
from app.schemas.github import (
    GitHubCommitDetail,
    GitHubCommitSummary,
    GitHubPullRequestDetail,
    GitHubPullRequestFile,
    GitHubPullRequestSummary,
)
from app.schemas.incident import IncidentCreate, IncidentResponse, IncidentStatus, Severity
from app.schemas.investigation import (
    InvestigationAcceptedResponse,
    InvestigationJobResponse,
    InvestigationJobStatus,
    InvestigationResponse,
    InvestigationReviewCreate,
    InvestigationReviewDecision,
    InvestigationReviewResponse,
    InvestigationStage,
    InvestigationStatus,
    PreliminaryInvestigationResult,
)
from app.schemas.llm import ChatMessage, ModelToolCall, ModelTurn, ToolDefinition
from app.services.incidents import IncidentNotFoundError
from app.services.investigations import (
    InvestigationExecutionError,
    InvestigationReviewNotAllowedError,
    InvestigationService,
    RepositoryContextRequiredError,
)
from app.tools.github import (
    GitHubToolExecutor,
    MalformedToolArgumentsError,
    ToolExecutionContext,
    UnknownToolError,
)
from tests.conftest import FakeIncidentRepository

NOW = datetime(2026, 8, 5, 8, 0, tzinfo=UTC)


async def _await_value[T](value: Awaitable[T]) -> T:
    return await value


def run_async[T](value: Awaitable[T]) -> T:
    return asyncio.run(_await_value(value))


def make_incident(repository: str | None = "openai/openai-python") -> IncidentResponse:
    return IncidentResponse(
        id=uuid4(),
        title="Checkout failures after SDK update",
        description="Requests began failing after a recent deployment.",
        severity=Severity.HIGH,
        status=IncidentStatus.OPEN,
        started_at=NOW,
        created_at=NOW,
        updated_at=NOW,
        repository_full_name=repository,
    )


class MemoryIncidentRepository:
    def __init__(self, incident: IncidentResponse | None) -> None:
        self.incident = incident

    async def create(self, _incident: IncidentCreate) -> IncidentResponse:
        raise AssertionError("not used by investigation tests")

    async def list(self) -> list[IncidentResponse]:
        return [self.incident] if self.incident else []

    async def get(self, incident_id: UUID) -> IncidentResponse | None:
        if self.incident and self.incident.id == incident_id:
            return self.incident
        return None


class MemoryEvidenceRepository:
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
            item_id
            for item_id in evidence_ids
            if (item := self.items.get(item_id)) is not None
            and item.incident_id == incident_id
            and item.investigation_id == investigation_id
        }


class MemoryInvestigationRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, InvestigationResponse] = {}
        self.progress_history: list[InvestigationStage] = []

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
            supporting_evidence_ids=[],
            missing_information=[],
            recommended_next_steps=[],
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
        self.progress_history.append(stage)
        stored = self.items[investigation_id].model_copy(
            update={"status": status, "stage": stage, "updated_at": datetime.now(UTC)}
        )
        self.items[investigation_id] = stored
        return stored

    async def get(self, investigation_id: UUID) -> InvestigationResponse | None:
        return self.items.get(investigation_id)

    async def list_for_incident(self, incident_id: UUID) -> list[InvestigationResponse]:
        return [item for item in self.items.values() if item.incident_id == incident_id]


class MemoryJobRepository:
    def __init__(self, investigations: MemoryInvestigationRepository) -> None:
        self.investigations = investigations
        self.items: dict[UUID, InvestigationJobResponse] = {}
        self._lock = asyncio.Lock()

    async def enqueue(
        self,
        incident_id: UUID,
        prompt_version: str,
        model_name: str,
        max_attempts: int,
    ) -> InvestigationAcceptedResponse:
        async with self._lock:
            active = next(
                (
                    item
                    for item in self.investigations.items.values()
                    if item.incident_id == incident_id
                    and item.status
                    in {InvestigationStatus.PENDING, InvestigationStatus.IN_PROGRESS}
                ),
                None,
            )
            if active is not None:
                return InvestigationAcceptedResponse(
                    investigation_id=active.id,
                    status=active.status,
                    stage=active.stage,
                    created_at=active.created_at,
                    already_active=True,
                )
            investigation = await self.investigations.create(
                incident_id,
                prompt_version,
                model_name,
            )
            now = datetime.now(UTC)
            job = InvestigationJobResponse(
                id=uuid4(),
                investigation_id=investigation.id,
                status=InvestigationJobStatus.QUEUED,
                attempt_count=0,
                max_attempts=max_attempts,
                next_attempt_at=now,
                locked_at=None,
                lease_expires_at=None,
                last_error=None,
                created_at=now,
                updated_at=now,
                completed_at=None,
            )
            self.items[job.id] = job
            return InvestigationAcceptedResponse(
                investigation_id=investigation.id,
                status=investigation.status,
                stage=investigation.stage,
                created_at=investigation.created_at,
            )

    async def claim(self, lease_seconds: int) -> InvestigationJobResponse | None:
        async with self._lock:
            now = datetime.now(UTC)
            eligible = [
                item
                for item in self.items.values()
                if item.attempt_count < item.max_attempts
                and (
                    (
                        item.status
                        in {InvestigationJobStatus.QUEUED, InvestigationJobStatus.RETRY_SCHEDULED}
                        and item.next_attempt_at <= now
                    )
                    or (
                        item.status is InvestigationJobStatus.RUNNING
                        and item.lease_expires_at is not None
                        and item.lease_expires_at <= now
                    )
                )
            ]
            if not eligible:
                return None
            selected = min(eligible, key=lambda item: (item.next_attempt_at, item.created_at))
            reclaimed = selected.status is InvestigationJobStatus.RUNNING
            claimed = selected.model_copy(
                update={
                    "status": InvestigationJobStatus.RUNNING,
                    "attempt_count": selected.attempt_count + 1,
                    "locked_at": now,
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                    "updated_at": now,
                    "reclaimed_stale_lease": reclaimed,
                }
            )
            self.items[claimed.id] = claimed
            return claimed

    async def complete(self, job_id: UUID) -> InvestigationJobResponse:
        return self._update(
            job_id,
            status=InvestigationJobStatus.COMPLETED,
            completed_at=datetime.now(UTC),
            locked_at=None,
            lease_expires_at=None,
            last_error=None,
        )

    async def schedule_retry(
        self,
        job_id: UUID,
        error_message: str,
        next_attempt_at: datetime,
    ) -> InvestigationJobResponse:
        return self._update(
            job_id,
            status=InvestigationJobStatus.RETRY_SCHEDULED,
            next_attempt_at=next_attempt_at,
            locked_at=None,
            lease_expires_at=None,
            last_error=error_message,
        )

    async def fail(self, job_id: UUID, error_message: str) -> InvestigationJobResponse:
        return self._update(
            job_id,
            status=InvestigationJobStatus.FAILED,
            completed_at=datetime.now(UTC),
            locked_at=None,
            lease_expires_at=None,
            last_error=error_message,
        )

    def _update(self, job_id: UUID, **updates: object) -> InvestigationJobResponse:
        stored = self.items[job_id].model_copy(update={**updates, "updated_at": datetime.now(UTC)})
        self.items[job_id] = stored
        return stored


class MemoryReviewRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, InvestigationReviewResponse] = {}

    async def upsert(
        self,
        investigation_id: UUID,
        review: InvestigationReviewCreate,
    ) -> InvestigationReviewResponse:
        now = datetime.now(UTC)
        existing = self.items.get(investigation_id)
        stored = InvestigationReviewResponse(
            id=existing.id if existing else uuid4(),
            investigation_id=investigation_id,
            decision=review.decision,
            note=review.note,
            reviewed_at=now,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        self.items[investigation_id] = stored
        return stored

    async def get(self, investigation_id: UUID) -> InvestigationReviewResponse | None:
        return self.items.get(investigation_id)


class FakeGitHubClient:
    def __init__(self, failure: Exception | None = None) -> None:
        self.calls: list[str] = []
        self.failure = failure

    def _record(self, name: str) -> None:
        self.calls.append(name)
        if self.failure:
            raise self.failure

    async def list_recent_commits(
        self,
        _repository: str,
        *,
        since: str | None,
        limit: int,
    ) -> list[GitHubCommitSummary]:
        self._record("list_recent_commits")
        assert since is None
        assert 1 <= limit <= 10
        return [
            GitHubCommitSummary(
                sha="a" * 40,
                message="Tighten checkout timeout",
                author="octocat",
                timestamp=NOW,
                html_url="https://github.com/openai/openai-python/commit/" + "a" * 40,
            )
        ]

    async def get_commit(self, _repository: str, sha: str) -> GitHubCommitDetail:
        self._record("get_commit")
        return GitHubCommitDetail(
            sha=sha,
            message="Tighten checkout timeout",
            author="octocat",
            timestamp=NOW,
            html_url="https://github.com/commit/" + sha,
            additions=12,
            deletions=3,
            total_changes=15,
            files=[],
        )

    async def list_recent_pull_requests(
        self,
        _repository: str,
        *,
        limit: int,
    ) -> list[GitHubPullRequestSummary]:
        self._record("list_recent_pull_requests")
        assert 1 <= limit <= 10
        return [self._pull_summary()]

    async def get_pull_request(
        self,
        _repository: str,
        pull_number: int,
    ) -> GitHubPullRequestDetail:
        self._record("get_pull_request")
        return GitHubPullRequestDetail(
            **self._pull_summary(pull_number).model_dump(),
            additions=20,
            deletions=4,
            changed_files=2,
            commits=1,
            merge_commit_sha="b" * 40,
        )

    async def get_pull_request_files(
        self,
        _repository: str,
        pull_number: int,
    ) -> list[GitHubPullRequestFile]:
        self._record("get_pull_request_files")
        return [
            GitHubPullRequestFile(
                sha="c" * 40,
                filename=f"pull-{pull_number}.py",
                status="modified",
                additions=4,
                deletions=1,
                changes=5,
                patch="@@ -1 +1 @@",
            )
        ]

    @staticmethod
    def _pull_summary(number: int = 42) -> GitHubPullRequestSummary:
        return GitHubPullRequestSummary(
            number=number,
            title="Change retry behavior",
            description="Updates the request retry policy.",
            state="closed",
            author="octocat",
            created_at=NOW,
            updated_at=NOW,
            merged_at=NOW,
            html_url=f"https://github.com/openai/openai-python/pull/{number}",
        )


class ToolThenConclusionLLM:
    provider_name = "test"
    model_name = "test-model"

    def __init__(
        self,
        tool_name: str = "list_recent_commits",
        arguments: str = '{"limit":1}',
        cited_id: UUID | None = None,
        invalid_final: str | None = None,
        culprit_id: str | None = None,
    ) -> None:
        self.tool_name = tool_name
        self.arguments = arguments
        self.cited_id = cited_id
        self.invalid_final = invalid_final
        self.culprit_id = culprit_id
        self.calls = 0
        self.advertised_tool_names: list[str] = []

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
    ) -> ModelTurn:
        self.calls += 1
        self.advertised_tool_names = [tool.function.name for tool in tools]
        if self.calls == 1:
            return ModelTurn(
                tool_calls=[
                    ModelToolCall(
                        id="tool-call-1",
                        name=self.tool_name,
                        arguments=self.arguments,
                    )
                ]
            )
        if self.invalid_final is not None:
            return ModelTurn(content=self.invalid_final)
        tool_messages = [message for message in messages if message.role == "tool"]
        tool_payload = json.loads(tool_messages[-1].content or "{}")
        cited_id = self.cited_id
        if cited_id is None:
            cited_id = UUID(tool_payload["evidence"][0]["evidence_id"])
        return ModelTurn(
            content=json.dumps(
                {
                    "summary": "A recent repository change is temporally relevant.",
                    "confidence": 0.62,
                    "suspected_change": "The retry policy change may be related.",
                    "suspected_culprit_id": self.culprit_id
                    or tool_payload["evidence"][0]["source_reference"],
                    "supporting_evidence_ids": [str(cited_id)],
                    "missing_information": ["Runtime logs are not available."],
                    "recommended_next_steps": ["Compare deployment and commit times."],
                }
            )
        )


class FailingLLM:
    provider_name = "test"
    model_name = "test-model"

    async def complete(
        self,
        _messages: list[ChatMessage],
        _tools: list[ToolDefinition],
    ) -> ModelTurn:
        raise LLMUnavailableError("provider unavailable")


class LoopingLLM:
    provider_name = "test"
    model_name = "test-model"

    async def complete(
        self,
        _messages: list[ChatMessage],
        _tools: list[ToolDefinition],
    ) -> ModelTurn:
        return ModelTurn(
            tool_calls=[
                ModelToolCall(
                    id=str(uuid4()),
                    name="list_recent_commits",
                    arguments='{"limit":1}',
                )
            ]
        )


def make_service(
    incident: IncidentResponse | None,
    llm: ToolThenConclusionLLM | FailingLLM | LoopingLLM,
    *,
    github: FakeGitHubClient | None = None,
    evidence: MemoryEvidenceRepository | None = None,
    investigations: MemoryInvestigationRepository | None = None,
    jobs: MemoryJobRepository | None = None,
    reviews: MemoryReviewRepository | None = None,
    max_tool_calls: int = 6,
    max_job_attempts: int = 3,
) -> tuple[InvestigationService, MemoryEvidenceRepository, MemoryInvestigationRepository]:
    evidence_repository = evidence or MemoryEvidenceRepository()
    investigation_repository = investigations or MemoryInvestigationRepository()
    github_client = github or FakeGitHubClient()
    incident_repository: IncidentRepository = MemoryIncidentRepository(incident)
    evidence_contract: EvidenceRepository = evidence_repository
    investigation_contract: InvestigationRepository = investigation_repository
    job_repository = jobs or MemoryJobRepository(investigation_repository)
    review_repository = reviews or MemoryReviewRepository()
    job_contract: InvestigationJobRepository = job_repository
    review_contract: InvestigationReviewRepository = review_repository
    service = InvestigationService(
        incident_repository,
        investigation_contract,
        evidence_contract,
        job_contract,
        review_contract,
        GitHubToolExecutor(github_client, evidence_contract),
        llm,
        max_tool_calls=max_tool_calls,
        final_output_retries=1,
        max_job_attempts=max_job_attempts,
    )
    return service, evidence_repository, investigation_repository


def test_successful_investigation_persists_commit_evidence() -> None:
    incident = make_incident()
    github = FakeGitHubClient()
    service, evidence, investigations = make_service(
        incident,
        ToolThenConclusionLLM(),
        github=github,
    )

    result = run_async(service.run(incident.id))

    assert result.status is InvestigationStatus.COMPLETED
    assert result.confidence == 0.62
    assert github.calls == ["list_recent_commits"]
    assert len(evidence.items) == 1
    stored = next(iter(evidence.items.values()))
    assert stored.source_type.value == "github_commit"
    assert result.supporting_evidence_ids == [stored.id]
    assert result.stage is InvestigationStage.COMPLETED
    assert investigations.progress_history == [
        InvestigationStage.COLLECTING_EVIDENCE,
        InvestigationStage.COLLECTING_EVIDENCE,
        InvestigationStage.REASONING,
        InvestigationStage.FINALIZING,
    ]


def test_service_can_advertise_only_tools_implemented_by_its_executor() -> None:
    incident = make_incident()
    llm = ToolThenConclusionLLM()
    evidence = MemoryEvidenceRepository()
    investigations = MemoryInvestigationRepository()
    jobs = MemoryJobRepository(investigations)
    service = InvestigationService(
        MemoryIncidentRepository(incident),
        investigations,
        evidence,
        jobs,
        MemoryReviewRepository(),
        GitHubToolExecutor(FakeGitHubClient(), evidence),
        llm,
        tool_definitions=GITHUB_TOOL_DEFINITIONS,
    )

    result = run_async(service.run(incident.id))

    assert result.status is InvestigationStatus.COMPLETED
    assert "search_knowledge" not in llm.advertised_tool_names
    assert set(llm.advertised_tool_names) == {
        "list_recent_commits",
        "get_commit",
        "list_recent_pull_requests",
        "get_pull_request",
        "get_pull_request_files",
    }


def test_llm_can_request_pull_request_tool() -> None:
    incident = make_incident()
    github = FakeGitHubClient()
    service, evidence, _investigations = make_service(
        incident,
        ToolThenConclusionLLM("get_pull_request", '{"pull_number":42}'),
        github=github,
    )

    result = run_async(service.run(incident.id))

    assert result.status is InvestigationStatus.COMPLETED
    assert github.calls == ["get_pull_request"]
    assert next(iter(evidence.items.values())).source_type.value == "github_pull_request"


def test_unknown_tool_is_rejected() -> None:
    evidence = MemoryEvidenceRepository()
    executor = GitHubToolExecutor(FakeGitHubClient(), evidence)
    context = ToolExecutionContext(uuid4(), uuid4(), "openai/openai-python")

    with pytest.raises(UnknownToolError):
        run_async(executor.execute("shell", "{}", context))


@pytest.mark.parametrize("arguments", ["not-json", "[]", '{"limit":1,"extra":true}'])
def test_malformed_tool_arguments_are_rejected(arguments: str) -> None:
    executor = GitHubToolExecutor(FakeGitHubClient(), MemoryEvidenceRepository())
    context = ToolExecutionContext(uuid4(), uuid4(), "openai/openai-python")

    with pytest.raises(MalformedToolArgumentsError):
        run_async(executor.execute("list_recent_commits", arguments, context))


def test_github_404_marks_investigation_failed() -> None:
    incident = make_incident()
    investigations = MemoryInvestigationRepository()
    service, _evidence, _ = make_service(
        incident,
        ToolThenConclusionLLM(),
        github=FakeGitHubClient(GitHubNotFoundError("not found")),
        investigations=investigations,
    )

    with pytest.raises(InvestigationExecutionError):
        run_async(service.run(incident.id))

    assert next(iter(investigations.items.values())).status is InvestigationStatus.FAILED


def test_llm_provider_failure_marks_investigation_failed() -> None:
    incident = make_incident()
    investigations = MemoryInvestigationRepository()
    service, _evidence, _ = make_service(
        incident,
        FailingLLM(),
        investigations=investigations,
    )

    with pytest.raises(InvestigationExecutionError):
        run_async(service.run(incident.id))

    assert next(iter(investigations.items.values())).status is InvestigationStatus.FAILED


def test_invalid_structured_final_output_fails_after_retry() -> None:
    incident = make_incident()
    llm = ToolThenConclusionLLM(invalid_final="not-json")
    service, _evidence, investigations = make_service(incident, llm)

    with pytest.raises(InvestigationExecutionError):
        run_async(service.run(incident.id))

    assert llm.calls == 3
    assert next(iter(investigations.items.values())).status is InvestigationStatus.FAILED


def test_confidence_outside_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PreliminaryInvestigationResult.model_validate(
            {
                "summary": "Invalid confidence",
                "confidence": 1.01,
                "suspected_change": None,
                "supporting_evidence_ids": [],
                "missing_information": ["Logs"],
                "recommended_next_steps": ["Inspect logs"],
            }
        )


def test_invented_evidence_uuid_is_rejected() -> None:
    incident = make_incident()
    service, _evidence, investigations = make_service(
        incident,
        ToolThenConclusionLLM(cited_id=uuid4()),
    )

    with pytest.raises(InvestigationExecutionError):
        run_async(service.run(incident.id))

    assert next(iter(investigations.items.values())).status is InvestigationStatus.FAILED


def test_evidence_from_another_incident_is_rejected() -> None:
    incident = make_incident()
    evidence = MemoryEvidenceRepository()
    foreign = EvidenceResponse(
        id=uuid4(),
        incident_id=uuid4(),
        investigation_id=uuid4(),
        source_type=EvidenceSourceType.GITHUB_COMMIT,
        source_reference="other/repository@abc",
        content='{"message":"foreign"}',
        metadata={},
        collected_at=NOW,
    )
    evidence.items[foreign.id] = foreign
    service, _evidence, investigations = make_service(
        incident,
        ToolThenConclusionLLM(cited_id=foreign.id),
        evidence=evidence,
    )

    with pytest.raises(InvestigationExecutionError):
        run_async(service.run(incident.id))

    assert next(iter(investigations.items.values())).status is InvestigationStatus.FAILED


def test_invented_culprit_source_reference_is_rejected() -> None:
    incident = make_incident()
    service, _evidence, investigations = make_service(
        incident,
        ToolThenConclusionLLM(culprit_id="attacker/repository@invented"),
    )

    with pytest.raises(InvestigationExecutionError):
        run_async(service.run(incident.id))

    assert next(iter(investigations.items.values())).status is InvestigationStatus.FAILED


def test_maximum_tool_call_loop_is_enforced() -> None:
    incident = make_incident()
    service, evidence, investigations = make_service(
        incident,
        LoopingLLM(),
        max_tool_calls=2,
    )

    with pytest.raises(InvestigationExecutionError, match="2-tool-call limit"):
        run_async(service.run(incident.id))

    assert len(evidence.items) == 2
    assert next(iter(investigations.items.values())).status is InvestigationStatus.FAILED


def test_missing_incident_is_rejected() -> None:
    service, _evidence, _investigations = make_service(None, ToolThenConclusionLLM())

    with pytest.raises(IncidentNotFoundError, match="was not found"):
        run_async(service.run(uuid4()))


def test_incident_without_repository_is_rejected_before_investigation_creation() -> None:
    incident = make_incident(None)
    service, _evidence, investigations = make_service(incident, ToolThenConclusionLLM())

    with pytest.raises(RepositoryContextRequiredError):
        run_async(service.run(incident.id))

    assert investigations.items == {}


def test_duplicate_active_enqueue_is_idempotent_and_rerun_after_completion_is_new() -> None:
    incident = make_incident()
    investigations = MemoryInvestigationRepository()
    jobs = MemoryJobRepository(investigations)
    service, _evidence, _ = make_service(
        incident,
        ToolThenConclusionLLM(),
        investigations=investigations,
        jobs=jobs,
    )

    first = run_async(service.enqueue(incident.id))
    duplicate = run_async(service.enqueue(incident.id))

    assert duplicate.investigation_id == first.investigation_id
    assert duplicate.already_active is True
    assert len(jobs.items) == 1

    run_async(service.execute(first.investigation_id))
    rerun = run_async(service.enqueue(incident.id))

    assert rerun.investigation_id != first.investigation_id
    assert rerun.already_active is False
    assert len(jobs.items) == 2


def test_human_review_is_separate_and_does_not_mutate_model_output() -> None:
    incident = make_incident()
    service, _evidence, _investigations = make_service(
        incident,
        ToolThenConclusionLLM(),
    )
    completed = run_async(service.run(incident.id))
    original_summary = completed.summary

    rejected = run_async(
        service.review(
            completed.id,
            InvestigationReviewCreate(
                decision=InvestigationReviewDecision.REJECTED,
                note="The deployment evidence is incomplete.",
            ),
        )
    )
    reloaded = run_async(service.get(completed.id))

    assert rejected.decision is InvestigationReviewDecision.REJECTED
    assert reloaded.review == rejected
    assert reloaded.summary == original_summary


def test_pending_investigation_cannot_be_reviewed() -> None:
    incident = make_incident()
    service, _evidence, _investigations = make_service(
        incident,
        ToolThenConclusionLLM(),
    )
    accepted = run_async(service.enqueue(incident.id))

    with pytest.raises(InvestigationReviewNotAllowedError, match="Only completed"):
        run_async(
            service.review(
                accepted.investigation_id,
                InvestigationReviewCreate(decision=InvestigationReviewDecision.ACCEPTED),
            )
        )


def test_investigation_http_endpoints(
    client: TestClient,
    repository: FakeIncidentRepository,
) -> None:
    created = client.post(
        "/api/v1/incidents",
        json={
            "title": "Checkout error spike",
            "description": "Customers receive HTTP 500 during checkout.",
            "severity": "high",
            "started_at": "2026-08-05T08:30:00Z",
            "repository_full_name": "openai/openai-python",
        },
    ).json()
    incident = run_async(repository.get(UUID(created["id"])))
    assert incident is not None
    llm = ToolThenConclusionLLM()
    service, _evidence, _investigations = make_service(incident, llm)

    def override_service() -> InvestigationService:
        return service

    from app.main import app

    app.dependency_overrides[get_investigation_service] = override_service
    started = time.perf_counter()
    run_response = client.post(f"/api/v1/incidents/{incident.id}/investigations")
    response_latency_ms = (time.perf_counter() - started) * 1_000
    assert run_response.status_code == 202
    assert response_latency_ms < 100
    assert run_response.json()["stage"] == "queued"
    assert run_response.json()["already_active"] is False
    assert llm.calls == 0
    investigation_id = run_response.json()["investigation_id"]
    run_async(service.execute(UUID(investigation_id)))

    evidence_response = client.get(f"/api/v1/incidents/{incident.id}/evidence")
    investigation_list = client.get(f"/api/v1/incidents/{incident.id}/investigations")
    investigation_response = client.get(f"/api/v1/investigations/{investigation_id}")

    assert evidence_response.status_code == 200
    assert evidence_response.json()["count"] == 1
    assert investigation_list.status_code == 200
    assert investigation_list.json()["count"] == 1
    assert investigation_response.status_code == 200
    assert investigation_response.json()["status"] == "completed"

    review_response = client.post(
        f"/api/v1/investigations/{investigation_id}/review",
        json={"decision": "accepted", "note": "Matches the deployment timeline."},
    )
    assert review_response.status_code == 200
    assert review_response.json()["decision"] == "accepted"

    invalid_review = client.post(
        f"/api/v1/investigations/{investigation_id}/review",
        json={"decision": "maybe"},
    )
    assert invalid_review.status_code == 422
