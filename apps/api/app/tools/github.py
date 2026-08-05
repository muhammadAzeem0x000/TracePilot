import json
from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.integrations.github import GitHubClientProtocol
from app.repositories.evidence import EvidenceRepository
from app.schemas.evidence import EvidenceCreate, EvidenceResponse, EvidenceSourceType
from app.schemas.github import (
    GetCommitArguments,
    GitHubCommitDetail,
    GitHubCommitSummary,
    GitHubPullRequestDetail,
    GitHubPullRequestFile,
    GitHubPullRequestSummary,
    ListRecentCommitsArguments,
    ListRecentPullRequestsArguments,
    PullRequestArguments,
)


class UnknownToolError(Exception):
    pass


class MalformedToolArgumentsError(Exception):
    pass


@dataclass(frozen=True)
class ToolExecutionContext:
    incident_id: UUID
    investigation_id: UUID
    repository_full_name: str


class GitHubToolExecutor:
    ALLOWED_TOOL_NAMES = frozenset(
        {
            "list_recent_commits",
            "get_commit",
            "list_recent_pull_requests",
            "get_pull_request",
            "get_pull_request_files",
        }
    )

    def __init__(
        self,
        github: GitHubClientProtocol,
        evidence_repository: EvidenceRepository,
    ) -> None:
        self._github = github
        self._evidence_repository = evidence_repository

    async def execute(
        self,
        tool_name: str,
        raw_arguments: str,
        context: ToolExecutionContext,
    ) -> list[EvidenceResponse]:
        if tool_name not in self.ALLOWED_TOOL_NAMES:
            raise UnknownToolError(f"Tool is not allowed: {tool_name}")
        arguments = self._parse_json_arguments(raw_arguments)

        try:
            if tool_name == "list_recent_commits":
                parsed = ListRecentCommitsArguments.model_validate(arguments)
                items = await self._github.list_recent_commits(
                    context.repository_full_name,
                    since=parsed.since.isoformat() if parsed.since else None,
                    limit=parsed.limit,
                )
                return await self._persist_commits(items, context, tool_name)
            if tool_name == "get_commit":
                parsed_commit = GetCommitArguments.model_validate(arguments)
                commit = await self._github.get_commit(
                    context.repository_full_name,
                    parsed_commit.sha,
                )
                return [await self._persist_commit(commit, context, tool_name)]
            if tool_name == "list_recent_pull_requests":
                parsed_pulls = ListRecentPullRequestsArguments.model_validate(arguments)
                pulls = await self._github.list_recent_pull_requests(
                    context.repository_full_name,
                    limit=parsed_pulls.limit,
                )
                return await self._persist_pulls(pulls, context, tool_name)
            parsed_pull = PullRequestArguments.model_validate(arguments)
            if tool_name == "get_pull_request":
                pull = await self._github.get_pull_request(
                    context.repository_full_name,
                    parsed_pull.pull_number,
                )
                return [await self._persist_pull(pull, context, tool_name)]
            files = await self._github.get_pull_request_files(
                context.repository_full_name,
                parsed_pull.pull_number,
            )
            return await self._persist_files(
                files,
                context,
                parsed_pull.pull_number,
                tool_name,
            )
        except ValidationError as exc:
            raise MalformedToolArgumentsError("Tool arguments failed validation") from exc

    @staticmethod
    def _parse_json_arguments(raw_arguments: str) -> object:
        try:
            arguments: object = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise MalformedToolArgumentsError("Tool arguments are not valid JSON") from exc
        if not isinstance(arguments, dict):
            raise MalformedToolArgumentsError("Tool arguments must be a JSON object")
        return arguments

    async def _persist_commits(
        self,
        commits: list[GitHubCommitSummary],
        context: ToolExecutionContext,
        tool_name: str,
    ) -> list[EvidenceResponse]:
        if not commits:
            return [
                await self._persist_empty_search(
                    context,
                    EvidenceSourceType.GITHUB_COMMIT_SEARCH,
                    f"{context.repository_full_name}@recent-commits",
                    tool_name,
                )
            ]
        return [await self._persist_commit(item, context, tool_name) for item in commits]

    async def _persist_commit(
        self,
        commit: GitHubCommitSummary | GitHubCommitDetail,
        context: ToolExecutionContext,
        tool_name: str,
    ) -> EvidenceResponse:
        return await self._persist_model(
            commit,
            context,
            EvidenceSourceType.GITHUB_COMMIT,
            f"{context.repository_full_name}@{commit.sha}",
            {"tool_name": tool_name, "sha": commit.sha},
        )

    async def _persist_pulls(
        self,
        pulls: list[GitHubPullRequestSummary],
        context: ToolExecutionContext,
        tool_name: str,
    ) -> list[EvidenceResponse]:
        if not pulls:
            return [
                await self._persist_empty_search(
                    context,
                    EvidenceSourceType.GITHUB_PULL_REQUEST_SEARCH,
                    f"{context.repository_full_name}#recent-pull-requests",
                    tool_name,
                )
            ]
        return [await self._persist_pull(item, context, tool_name) for item in pulls]

    async def _persist_pull(
        self,
        pull: GitHubPullRequestSummary | GitHubPullRequestDetail,
        context: ToolExecutionContext,
        tool_name: str,
    ) -> EvidenceResponse:
        return await self._persist_model(
            pull,
            context,
            EvidenceSourceType.GITHUB_PULL_REQUEST,
            f"{context.repository_full_name}#{pull.number}",
            {"tool_name": tool_name, "pull_number": pull.number},
        )

    async def _persist_files(
        self,
        files: list[GitHubPullRequestFile],
        context: ToolExecutionContext,
        pull_number: int,
        tool_name: str,
    ) -> list[EvidenceResponse]:
        if not files:
            return [
                await self._persist_empty_search(
                    context,
                    EvidenceSourceType.GITHUB_PULL_REQUEST_SEARCH,
                    f"{context.repository_full_name}#{pull_number}/files",
                    tool_name,
                )
            ]
        return [
            await self._persist_model(
                item,
                context,
                EvidenceSourceType.GITHUB_PULL_REQUEST_FILE,
                f"{context.repository_full_name}#{pull_number}/file/{item.sha}",
                {
                    "tool_name": tool_name,
                    "pull_number": pull_number,
                    "filename": item.filename,
                },
            )
            for item in files
        ]

    async def _persist_empty_search(
        self,
        context: ToolExecutionContext,
        source_type: EvidenceSourceType,
        source_reference: str,
        tool_name: str,
    ) -> EvidenceResponse:
        evidence = EvidenceCreate(
            incident_id=context.incident_id,
            investigation_id=context.investigation_id,
            source_type=source_type,
            source_reference=source_reference,
            content='{"items":[]}',
            metadata={"tool_name": tool_name, "repository": context.repository_full_name},
        )
        return await self._evidence_repository.create(evidence)

    async def _persist_model(
        self,
        model: BaseModel,
        context: ToolExecutionContext,
        source_type: EvidenceSourceType,
        source_reference: str,
        metadata: dict[str, str | int],
    ) -> EvidenceResponse:
        evidence = EvidenceCreate(
            incident_id=context.incident_id,
            investigation_id=context.investigation_id,
            source_type=source_type,
            source_reference=source_reference,
            content=model.model_dump_json(exclude_none=True),
            metadata={"repository": context.repository_full_name, **metadata},
        )
        return await self._evidence_repository.create(evidence)
