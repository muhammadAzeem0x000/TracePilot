import time
from datetime import UTC, datetime

from app.observability.tracing import record_operation
from app.repositories.operations import AIOperationRepository
from app.schemas.evidence import EvidenceResponse
from app.schemas.operations import AIOperationStatus, AIOperationType
from app.tools.github import ToolExecutionContext
from app.tools.investigation import InvestigationToolExecutorProtocol


class ObservedInvestigationToolExecutor:
    def __init__(
        self,
        executor: InvestigationToolExecutorProtocol,
        operations: AIOperationRepository,
    ) -> None:
        self._executor = executor
        self._operations = operations

    async def execute(
        self,
        tool_name: str,
        raw_arguments: str,
        context: ToolExecutionContext,
    ) -> list[EvidenceResponse]:
        operation_type = (
            AIOperationType.KNOWLEDGE_RETRIEVAL
            if tool_name == "search_knowledge"
            else AIOperationType.GITHUB_TOOL
        )
        started_at = datetime.now(UTC)
        started_perf = time.perf_counter()
        try:
            evidence = await self._executor.execute(tool_name, raw_arguments, context)
        except Exception as exc:
            await record_operation(
                self._operations,
                operation_type=operation_type,
                started_at=started_at,
                started_perf=started_perf,
                status=AIOperationStatus.FAILED,
                tool_name=tool_name,
                error_type=type(exc).__name__,
            )
            raise
        await record_operation(
            self._operations,
            operation_type=operation_type,
            started_at=started_at,
            started_perf=started_perf,
            status=AIOperationStatus.SUCCEEDED,
            tool_name=tool_name,
            metadata={"evidence_count": len(evidence)},
        )
        return evidence
