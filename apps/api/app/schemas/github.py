from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

GitSha = Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{7,40}$")]


class GitHubCommitSummary(BaseModel):
    sha: str
    message: str
    author: str | None
    timestamp: datetime | None
    html_url: str


class GitHubFileChange(BaseModel):
    filename: str
    status: str
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)
    changes: int = Field(ge=0)
    patch: str | None = None


class GitHubCommitDetail(GitHubCommitSummary):
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)
    total_changes: int = Field(ge=0)
    files: list[GitHubFileChange]


class GitHubPullRequestSummary(BaseModel):
    number: int = Field(gt=0)
    title: str
    description: str | None
    state: str
    author: str | None
    created_at: datetime
    updated_at: datetime
    merged_at: datetime | None
    html_url: str


class GitHubPullRequestDetail(GitHubPullRequestSummary):
    additions: int = Field(ge=0)
    deletions: int = Field(ge=0)
    changed_files: int = Field(ge=0)
    commits: int = Field(ge=0)
    merge_commit_sha: str | None


class GitHubPullRequestFile(GitHubFileChange):
    sha: str


class ListRecentCommitsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    since: AwareDatetime | None = None
    limit: int = Field(default=5, ge=1, le=10)


class GetCommitArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sha: GitSha


class ListRecentPullRequestsArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=5, ge=1, le=10)


class PullRequestArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pull_number: int = Field(gt=0)
