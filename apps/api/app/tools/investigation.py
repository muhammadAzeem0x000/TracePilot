from typing import Protocol

from app.schemas.evidence import EvidenceResponse
from app.tools.github import GitHubToolExecutor, ToolExecutionContext, UnknownToolError
from app.tools.knowledge import KnowledgeToolExecutor


class InvestigationToolExecutorProtocol(Protocol):
    async def execute(
        self,
        tool_name: str,
        raw_arguments: str,
        context: ToolExecutionContext,
    ) -> list[EvidenceResponse]: ...


class InvestigationToolExecutor:
    def __init__(
        self,
        github: GitHubToolExecutor,
        knowledge: KnowledgeToolExecutor,
    ) -> None:
        self._github = github
        self._knowledge = knowledge

    async def execute(
        self,
        tool_name: str,
        raw_arguments: str,
        context: ToolExecutionContext,
    ) -> list[EvidenceResponse]:
        if tool_name == self._knowledge.TOOL_NAME:
            return await self._knowledge.execute(raw_arguments, context)
        if tool_name in self._github.ALLOWED_TOOL_NAMES:
            return await self._github.execute(tool_name, raw_arguments, context)
        raise UnknownToolError(f"Tool is not allowed: {tool_name}")
