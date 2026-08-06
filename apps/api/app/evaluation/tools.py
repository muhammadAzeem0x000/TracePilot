import json

from pydantic import BaseModel, ValidationError

from app.evaluation.models import EvaluationEvidenceFixture, IncidentEvaluationScenario
from app.repositories.evidence import EvidenceRepository
from app.schemas.evidence import EvidenceCreate, EvidenceResponse, EvidenceSourceType
from app.schemas.github import (
    GetCommitArguments,
    ListRecentCommitsArguments,
    ListRecentPullRequestsArguments,
    PullRequestArguments,
)
from app.schemas.knowledge import SearchKnowledgeArguments
from app.tools.github import (
    MalformedToolArgumentsError,
    ToolExecutionContext,
    UnknownToolError,
)

ARGUMENT_MODELS: dict[str, type[BaseModel]] = {
    "list_recent_commits": ListRecentCommitsArguments,
    "get_commit": GetCommitArguments,
    "list_recent_pull_requests": ListRecentPullRequestsArguments,
    "get_pull_request": PullRequestArguments,
    "get_pull_request_files": PullRequestArguments,
    "search_knowledge": SearchKnowledgeArguments,
}


class ControlledEvaluationToolExecutor:
    """Allowlisted tool boundary backed by immutable scenario evidence fixtures."""

    def __init__(
        self,
        scenario: IncidentEvaluationScenario,
        evidence_repository: EvidenceRepository,
    ) -> None:
        self._scenario = scenario
        self._evidence = evidence_repository
        self.calls: list[str] = []

    async def execute(
        self,
        tool_name: str,
        raw_arguments: str,
        context: ToolExecutionContext,
    ) -> list[EvidenceResponse]:
        argument_model = ARGUMENT_MODELS.get(tool_name)
        if argument_model is None:
            raise UnknownToolError(f"Tool is not allowed: {tool_name}")
        try:
            raw: object = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise MalformedToolArgumentsError("Tool arguments are not valid JSON") from exc
        try:
            arguments = argument_model.model_validate(raw)
        except ValidationError as exc:
            raise MalformedToolArgumentsError("Tool arguments failed validation") from exc

        self.calls.append(tool_name)
        fixtures = [item for item in self._scenario.evidence if item.tool_name == tool_name]
        fixtures = self._filter_fixtures(tool_name, arguments, fixtures)
        persisted = [
            await self._evidence.create(
                EvidenceCreate(
                    incident_id=context.incident_id,
                    investigation_id=context.investigation_id,
                    source_type=item.source_type,
                    source_reference=item.source_reference,
                    content=item.content,
                    metadata={
                        **item.metadata,
                        "tool_name": tool_name,
                        "repository": context.repository_full_name,
                        "evaluation_scenario": self._scenario.id,
                    },
                )
            )
            for item in fixtures
        ]
        if persisted:
            return persisted
        return [await self._persist_empty_result(tool_name, context)]

    @staticmethod
    def _filter_fixtures(
        tool_name: str,
        arguments: BaseModel,
        fixtures: list[EvaluationEvidenceFixture],
    ) -> list[EvaluationEvidenceFixture]:
        if tool_name == "get_commit":
            sha = str(arguments.model_dump()["sha"])
            return [item for item in fixtures if item.metadata.get("sha") == sha]
        if tool_name in {"get_pull_request", "get_pull_request_files"}:
            number = int(arguments.model_dump()["pull_number"])
            return [item for item in fixtures if item.metadata.get("pull_number") == number]
        limit_key = "top_k" if tool_name == "search_knowledge" else "limit"
        limit = int(arguments.model_dump().get(limit_key, 5))
        return fixtures[:limit]

    async def _persist_empty_result(
        self,
        tool_name: str,
        context: ToolExecutionContext,
    ) -> EvidenceResponse:
        if tool_name == "search_knowledge":
            source_type = EvidenceSourceType.KNOWLEDGE_CHUNK
        elif "pull_request" in tool_name:
            source_type = EvidenceSourceType.GITHUB_PULL_REQUEST_SEARCH
        else:
            source_type = EvidenceSourceType.GITHUB_COMMIT_SEARCH
        return await self._evidence.create(
            EvidenceCreate(
                incident_id=context.incident_id,
                investigation_id=context.investigation_id,
                source_type=source_type,
                source_reference=f"evaluation/{self._scenario.id}/empty/{tool_name}",
                content='{"items":[]}',
                metadata={
                    "tool_name": tool_name,
                    "repository": context.repository_full_name,
                    "evaluation_scenario": self._scenario.id,
                },
            )
        )
