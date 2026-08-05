from typing import cast

from pydantic import BaseModel

from app.schemas.github import (
    GetCommitArguments,
    ListRecentCommitsArguments,
    ListRecentPullRequestsArguments,
    PullRequestArguments,
)
from app.schemas.knowledge import SearchKnowledgeArguments
from app.schemas.llm import ToolDefinition, ToolFunctionDefinition


def _tool(name: str, description: str, argument_model: type[BaseModel]) -> ToolDefinition:
    parameters = cast(dict[str, object], argument_model.model_json_schema())
    return ToolDefinition(
        function=ToolFunctionDefinition(
            name=name,
            description=description,
            parameters=parameters,
        )
    )


GITHUB_TOOL_DEFINITIONS = [
    _tool(
        "list_recent_commits",
        "List a small number of recent commits from the incident's configured repository.",
        ListRecentCommitsArguments,
    ),
    _tool(
        "get_commit",
        "Retrieve normalized details and changed-file metadata for one commit SHA.",
        GetCommitArguments,
    ),
    _tool(
        "list_recent_pull_requests",
        "List a small number of recent pull requests from the configured repository.",
        ListRecentPullRequestsArguments,
    ),
    _tool(
        "get_pull_request",
        "Retrieve normalized details for one pull request number.",
        PullRequestArguments,
    ),
    _tool(
        "get_pull_request_files",
        "Retrieve bounded changed-file metadata for one pull request number.",
        PullRequestArguments,
    ),
]

KNOWLEDGE_TOOL_DEFINITION = _tool(
    "search_knowledge",
    (
        "Search repository-scoped engineering runbooks, architecture, and past incidents. "
        "The application controls repository scope."
    ),
    SearchKnowledgeArguments,
)

INVESTIGATION_TOOL_DEFINITIONS = [*GITHUB_TOOL_DEFINITIONS, KNOWLEDGE_TOOL_DEFINITION]
