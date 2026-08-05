from collections.abc import Mapping
from datetime import datetime
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from app.schemas.github import (
    GitHubCommitDetail,
    GitHubCommitSummary,
    GitHubFileChange,
    GitHubPullRequestDetail,
    GitHubPullRequestFile,
    GitHubPullRequestSummary,
)


class GitHubError(Exception):
    """Base error for controlled GitHub failures."""


class GitHubAuthenticationError(GitHubError):
    pass


class GitHubPermissionError(GitHubError):
    pass


class GitHubNotFoundError(GitHubError):
    pass


class GitHubRateLimitError(GitHubError):
    pass


class GitHubUnavailableError(GitHubError):
    pass


class GitHubResponseError(GitHubError):
    pass


class GitHubClientProtocol(Protocol):
    async def list_recent_commits(
        self, repository: str, *, since: str | None, limit: int
    ) -> list[GitHubCommitSummary]: ...

    async def get_commit(self, repository: str, sha: str) -> GitHubCommitDetail: ...

    async def list_recent_pull_requests(
        self, repository: str, *, limit: int
    ) -> list[GitHubPullRequestSummary]: ...

    async def get_pull_request(
        self, repository: str, pull_number: int
    ) -> GitHubPullRequestDetail: ...

    async def get_pull_request_files(
        self, repository: str, pull_number: int
    ) -> list[GitHubPullRequestFile]: ...


class _RawUser(BaseModel):
    login: str


class _RawCommitAuthor(BaseModel):
    name: str | None = None
    date: datetime | None = None


class _RawCommitData(BaseModel):
    message: str
    author: _RawCommitAuthor | None = None


class _RawStats(BaseModel):
    additions: int = 0
    deletions: int = 0
    total: int = 0


class _RawFile(BaseModel):
    filename: str
    status: str
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    patch: str | None = None
    sha: str = ""


class _RawCommit(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sha: str
    commit: _RawCommitData
    author: _RawUser | None = None
    html_url: str
    stats: _RawStats | None = None
    files: list[_RawFile] = Field(default_factory=list)


class _RawPullRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    number: int
    title: str
    body: str | None = None
    state: str
    user: _RawUser | None = None
    created_at: datetime
    updated_at: datetime
    merged_at: datetime | None = None
    html_url: str
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    commits: int = 0
    merge_commit_sha: str | None = None


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value if len(value) <= limit else f"{value[:limit]}…"


class GitHubClient:
    def __init__(self, api_url: str, token: str) -> None:
        self._api_url = api_url
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "TracePilot/0.2",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> object:
        try:
            async with httpx.AsyncClient(
                base_url=self._api_url,
                headers=self._headers,
                timeout=15.0,
            ) as client:
                response = await client.get(path, params=params)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise GitHubUnavailableError("GitHub is unavailable") from exc

        if response.status_code == 401:
            raise GitHubAuthenticationError("GitHub rejected the configured token")
        if response.status_code == 403:
            if response.headers.get("x-ratelimit-remaining") == "0":
                raise GitHubRateLimitError("GitHub API rate limit exceeded")
            raise GitHubPermissionError("GitHub denied read access to the repository")
        if response.status_code == 404:
            raise GitHubNotFoundError("GitHub repository resource was not found")
        if response.status_code == 429:
            raise GitHubRateLimitError("GitHub API rate limit exceeded")
        if response.status_code >= 500:
            raise GitHubUnavailableError("GitHub is unavailable")
        if response.status_code >= 400:
            raise GitHubResponseError(f"Unexpected GitHub response: {response.status_code}")

        try:
            return response.json()
        except ValueError as exc:
            raise GitHubResponseError("GitHub returned invalid JSON") from exc

    async def list_recent_commits(
        self,
        repository: str,
        *,
        since: str | None,
        limit: int,
    ) -> list[GitHubCommitSummary]:
        params = {"per_page": str(limit)}
        if since:
            params["since"] = since
        raw = await self._request(f"/repos/{repository}/commits", params=params)
        try:
            commits = TypeAdapter(list[_RawCommit]).validate_python(raw)
        except ValidationError as exc:
            raise GitHubResponseError("GitHub returned an unexpected commit shape") from exc
        return [self._commit_summary(commit) for commit in commits]

    async def get_commit(self, repository: str, sha: str) -> GitHubCommitDetail:
        raw = await self._request(f"/repos/{repository}/commits/{sha}")
        try:
            commit = _RawCommit.model_validate(raw)
        except ValidationError as exc:
            raise GitHubResponseError("GitHub returned an unexpected commit shape") from exc
        summary = self._commit_summary(commit)
        stats = commit.stats or _RawStats()
        return GitHubCommitDetail(
            **summary.model_dump(),
            additions=stats.additions,
            deletions=stats.deletions,
            total_changes=stats.total,
            files=[self._file_change(item) for item in commit.files[:30]],
        )

    async def list_recent_pull_requests(
        self,
        repository: str,
        *,
        limit: int,
    ) -> list[GitHubPullRequestSummary]:
        raw = await self._request(
            f"/repos/{repository}/pulls",
            params={
                "state": "all",
                "sort": "updated",
                "direction": "desc",
                "per_page": str(limit),
            },
        )
        try:
            pulls = TypeAdapter(list[_RawPullRequest]).validate_python(raw)
        except ValidationError as exc:
            raise GitHubResponseError("GitHub returned an unexpected pull request shape") from exc
        return [self._pull_request_summary(item) for item in pulls]

    async def get_pull_request(
        self,
        repository: str,
        pull_number: int,
    ) -> GitHubPullRequestDetail:
        raw = await self._request(f"/repos/{repository}/pulls/{pull_number}")
        try:
            pull = _RawPullRequest.model_validate(raw)
        except ValidationError as exc:
            raise GitHubResponseError("GitHub returned an unexpected pull request shape") from exc
        summary = self._pull_request_summary(pull)
        return GitHubPullRequestDetail(
            **summary.model_dump(),
            additions=pull.additions,
            deletions=pull.deletions,
            changed_files=pull.changed_files,
            commits=pull.commits,
            merge_commit_sha=pull.merge_commit_sha,
        )

    async def get_pull_request_files(
        self,
        repository: str,
        pull_number: int,
    ) -> list[GitHubPullRequestFile]:
        raw = await self._request(
            f"/repos/{repository}/pulls/{pull_number}/files",
            params={"per_page": "30"},
        )
        try:
            files = TypeAdapter(list[_RawFile]).validate_python(raw)
        except ValidationError as exc:
            raise GitHubResponseError("GitHub returned an unexpected file shape") from exc
        return [
            GitHubPullRequestFile(sha=item.sha, **self._file_change(item).model_dump())
            for item in files
        ]

    @staticmethod
    def _commit_summary(commit: _RawCommit) -> GitHubCommitSummary:
        author = commit.author.login if commit.author else None
        if author is None and commit.commit.author:
            author = commit.commit.author.name
        timestamp = commit.commit.author.date if commit.commit.author else None
        return GitHubCommitSummary(
            sha=commit.sha,
            message=_truncate(commit.commit.message, 1_000) or "",
            author=author,
            timestamp=timestamp,
            html_url=commit.html_url,
        )

    @staticmethod
    def _file_change(item: _RawFile) -> GitHubFileChange:
        return GitHubFileChange(
            filename=item.filename,
            status=item.status,
            additions=item.additions,
            deletions=item.deletions,
            changes=item.changes,
            patch=_truncate(item.patch, 2_000),
        )

    @staticmethod
    def _pull_request_summary(pull: _RawPullRequest) -> GitHubPullRequestSummary:
        return GitHubPullRequestSummary(
            number=pull.number,
            title=_truncate(pull.title, 500) or "",
            description=_truncate(pull.body, 2_000),
            state=pull.state,
            author=pull.user.login if pull.user else None,
            created_at=pull.created_at,
            updated_at=pull.updated_at,
            merged_at=pull.merged_at,
            html_url=pull.html_url,
        )
