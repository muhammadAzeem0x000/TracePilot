import time
from datetime import UTC, datetime

from app.ai.embeddings import EmbeddingProvider, EmbeddingTask
from app.ai.provider import LLMProvider
from app.observability.pricing import PricingRegistry
from app.observability.tracing import current_operation_label, record_operation
from app.repositories.operations import AIOperationRepository
from app.schemas.llm import ChatMessage, ModelTurn, ToolDefinition
from app.schemas.operations import AIOperationStatus, AIOperationType


class ObservedLLMProvider:
    def __init__(
        self,
        provider: LLMProvider,
        operations: AIOperationRepository,
        pricing: PricingRegistry,
    ) -> None:
        self._provider = provider
        self._operations = operations
        self._pricing = pricing

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    async def complete(
        self,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
    ) -> ModelTurn:
        started_at = datetime.now(UTC)
        started_perf = time.perf_counter()
        label = current_operation_label()
        operation_type, prompt_version = label or (AIOperationType.LLM_CALL, None)
        try:
            turn = await self._provider.complete(messages, tools)
        except Exception as exc:
            await record_operation(
                self._operations,
                operation_type=operation_type,
                started_at=started_at,
                started_perf=started_perf,
                status=AIOperationStatus.FAILED,
                provider=self.provider_name,
                model=self.model_name,
                prompt_version=prompt_version,
                error_type=type(exc).__name__,
            )
            raise
        await record_operation(
            self._operations,
            operation_type=operation_type,
            started_at=started_at,
            started_perf=started_perf,
            status=AIOperationStatus.SUCCEEDED,
            provider=turn.provider or self.provider_name,
            model=turn.model or self.model_name,
            prompt_version=prompt_version,
            input_tokens=turn.input_tokens,
            output_tokens=turn.output_tokens,
            total_tokens=turn.total_tokens,
            estimated_cost_usd=self._pricing.estimate(
                turn.model or self.model_name,
                turn.input_tokens,
                turn.output_tokens,
            ),
            fallback_used=turn.fallback_used,
            fallback_reason=turn.fallback_reason,
            metadata={"pricing_source_date": self._pricing.source_date},
        )
        return turn


class ObservedEmbeddingProvider:
    def __init__(self, provider: EmbeddingProvider, operations: AIOperationRepository) -> None:
        self._provider = provider
        self._operations = operations

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    @property
    def dimensions(self) -> int:
        return self._provider.dimensions

    async def embed(self, texts: list[str], *, task: EmbeddingTask) -> list[list[float]]:
        started_at = datetime.now(UTC)
        started_perf = time.perf_counter()
        try:
            result = await self._provider.embed(texts, task=task)
        except Exception as exc:
            await record_operation(
                self._operations,
                operation_type=AIOperationType.EMBEDDING,
                started_at=started_at,
                started_perf=started_perf,
                status=AIOperationStatus.FAILED,
                provider="gemini",
                model=self.model_name,
                error_type=type(exc).__name__,
                metadata={"input_count": len(texts), "task": task.value},
            )
            raise
        await record_operation(
            self._operations,
            operation_type=AIOperationType.EMBEDDING,
            started_at=started_at,
            started_perf=started_perf,
            status=AIOperationStatus.SUCCEEDED,
            provider="gemini",
            model=self.model_name,
            metadata={"input_count": len(texts), "task": task.value},
        )
        return result
