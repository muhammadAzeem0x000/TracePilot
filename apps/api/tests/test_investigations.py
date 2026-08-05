import asyncio
import json
from collections.abc import Awaitable
from datetime import UTC, datetime
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
    InvestigationResponse,
    InvestigationStatus,
    PreliminaryInvestigationResult,
)
from app.schemas.llm import ChatMessage, ModelToolCall, ModelTurn, ToolDefinition
from app.services.incidents import IncidentNotFoundError
from app.services.investigations import (
    InvestigationExecutionError,
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
            status=InvestigationStatus.IN_PROGRESS,
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
    ) -> InvestigationResponse:
        now = datetime.now(UTC)
        stored = self.items[investigation_id].model_copy(
            update={
                **result.model_dump(),
                "status": InvestigationStatus.COMPLETED,
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
                "error_message": error_message,
                "completed_at": now,
                "updated_at": now,
            }
        )
        self.items[investigation_id] = stored
        return stored

    async def get(self, investigation_id: UUID) -> InvestigationResponse | None:
        return self.items.get(investigation_id)

    async def list_for_incident(self, incident_id: UUID) -> list[InvestigationResponse]:
        return [item for item in self.items.values() if item.incident_id == incident_id]


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
    model_name = "test-model"

    def __init__(
        self,
        tool_name: str = "list_recent_commits",
        arguments: str = '{"limit":1}',
        cited_id: UUID | None = None,
        invalid_final: str | None = None,
    ) -> None:
        self.tool_name = tool_name
        self.arguments = arguments
        self.cited_id = cited_id
        self.invalid_final = invalid_final
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
        cited_id = self.cited_id
        if cited_id is None:
            tool_messages = [message for message in messages if message.role == "tool"]
            tool_payload = json.loads(tool_messages[-1].content or "{}")
            cited_id = UUID(tool_payload["evidence"][0]["evidence_id"])
        return ModelTurn(
            content=json.dumps(
                {
                    "summary": "A recent repository change is temporally relevant.",
                    "confidence": 0.62,
                    "suspected_change": "The retry policy change may be related.",
                    "supporting_evidence_ids": [str(cited_id)],
                    "missing_information": ["Runtime logs are not available."],
                    "recommended_next_steps": ["Compare deployment and commit times."],
                }
            )
        )


class FailingLLM:
    model_name = "test-model"

    async def complete(
        self,
        _messages: list[ChatMessage],
        _tools: list[ToolDefinition],
    ) -> ModelTurn:
        raise LLMUnavailableError("provider unavailable")


class LoopingLLM:
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
    max_tool_calls: int = 6,
) -> tuple[InvestigationService, MemoryEvidenceRepository, MemoryInvestigationRepository]:
    evidence_repository = evidence or MemoryEvidenceRepository()
    investigation_repository = investigations or MemoryInvestigationRepository()
    github_client = github or FakeGitHubClient()
    incident_repository: IncidentRepository = MemoryIncidentRepository(incident)
    evidence_contract: EvidenceRepository = evidence_repository
    investigation_contract: InvestigationRepository = investigation_repository
    service = InvestigationService(
        incident_repository,
        investigation_contract,
        evidence_contract,
        GitHubToolExecutor(github_client, evidence_contract),
        llm,
        max_tool_calls=max_tool_calls,
        final_output_retries=1,
    )
    return service, evidence_repository, investigation_repository


def test_successful_investigation_persists_commit_evidence() -> None:
    incident = make_incident()
    github = FakeGitHubClient()
    service, evidence, _investigations = make_service(
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


def test_service_can_advertise_only_tools_implemented_by_its_executor() -> None:
    incident = make_incident()
    llm = ToolThenConclusionLLM()
    evidence = MemoryEvidenceRepository()
    investigations = MemoryInvestigationRepository()
    service = InvestigationService(
        MemoryIncidentRepository(incident),
        investigations,
        evidence,
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
    service, _evidence, _investigations = make_service(incident, ToolThenConclusionLLM())

    def override_service() -> InvestigationService:
        return service

    from app.main import app

    app.dependency_overrides[get_investigation_service] = override_service
    run_response = client.post(f"/api/v1/incidents/{incident.id}/investigations")
    assert run_response.status_code == 201
    investigation_id = run_response.json()["id"]

    evidence_response = client.get(f"/api/v1/incidents/{incident.id}/evidence")
    investigation_list = client.get(f"/api/v1/incidents/{incident.id}/investigations")
    investigation_response = client.get(f"/api/v1/investigations/{investigation_id}")

    assert evidence_response.status_code == 200
    assert evidence_response.json()["count"] == 1
    assert investigation_list.status_code == 200
    assert investigation_list.json()["count"] == 1
    assert investigation_response.status_code == 200
    assert investigation_response.json()["status"] == "completed"
