import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.repositories.incidents import RepositoryError
from app.repositories.operations import AIOperationRepository
from app.schemas.operations import AIOperationCreate, AIOperationStatus, AIOperationType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TraceContext:
    investigation_id: UUID
    job_id: UUID | None
    trace_id: UUID
    parent_span_id: UUID | None = None


_trace_context: ContextVar[TraceContext | None] = ContextVar("tracepilot_trace", default=None)
_operation_label: ContextVar[tuple[AIOperationType, str | None] | None] = ContextVar(
    "tracepilot_operation_label", default=None
)


def current_trace() -> TraceContext | None:
    return _trace_context.get()


def current_operation_label() -> tuple[AIOperationType, str | None] | None:
    return _operation_label.get()


def begin_trace(investigation_id: UUID, job_id: UUID | None = None) -> Token[TraceContext | None]:
    return _trace_context.set(TraceContext(investigation_id, job_id, uuid4()))


def end_trace(token: Token[TraceContext | None]) -> None:
    _trace_context.reset(token)


@asynccontextmanager
async def operation_label(
    operation_type: AIOperationType, prompt_version: str | None = None
) -> AsyncIterator[None]:
    token = _operation_label.set((operation_type, prompt_version))
    try:
        yield
    finally:
        _operation_label.reset(token)


async def record_operation(
    repository: AIOperationRepository,
    *,
    operation_type: AIOperationType,
    started_at: datetime,
    started_perf: float,
    status: AIOperationStatus,
    provider: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    tool_name: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    fallback_used: bool = False,
    fallback_reason: str | None = None,
    error_type: str | None = None,
    metadata: dict[str, str | int | float | bool | None] | None = None,
) -> None:
    trace = current_trace()
    if trace is None:
        return
    completed_at = datetime.now(UTC)
    try:
        await repository.create(
            AIOperationCreate(
                investigation_id=trace.investigation_id,
                job_id=trace.job_id,
                trace_id=trace.trace_id,
                span_id=uuid4(),
                parent_span_id=trace.parent_span_id,
                operation_type=operation_type,
                provider=provider,
                model=model,
                prompt_version=prompt_version,
                tool_name=tool_name,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=max(0, round((time.perf_counter() - started_perf) * 1_000)),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=estimated_cost_usd,
                fallback_used=fallback_used,
                fallback_reason=fallback_reason,
                status=status,
                error_type=error_type,
                metadata=metadata or {},
            )
        )
    except RepositoryError:
        logger.warning("ai_operation_persistence_failed", extra={"operation_type": operation_type})
