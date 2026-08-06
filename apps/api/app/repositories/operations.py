from collections import defaultdict
from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from app.db.supabase import StorageError, SupabaseRestClient
from app.repositories.incidents import RepositoryError
from app.schemas.operations import (
    AIOperationCreate,
    AIOperationResponse,
    AIOperationType,
    InvestigationMetricsResponse,
    LatencyMetric,
)


class AIOperationRepository(Protocol):
    async def create(self, operation: AIOperationCreate) -> AIOperationResponse: ...

    async def list_for_investigation(self, investigation_id: UUID) -> list[AIOperationResponse]: ...


class SupabaseAIOperationRepository:
    def __init__(self, client: SupabaseRestClient) -> None:
        self._client = client

    async def create(self, operation: AIOperationCreate) -> AIOperationResponse:
        try:
            records = await self._client.request(
                "POST",
                "/ai_operations",
                params={"select": "*"},
                json_body=operation.model_dump(mode="json"),
                prefer_representation=True,
            )
            if len(records) != 1:
                raise RepositoryError("Unable to record AI operation")
            return AIOperationResponse.model_validate(records[0])
        except (StorageError, ValidationError) as exc:
            raise RepositoryError("Unable to record AI operation") from exc

    async def list_for_investigation(self, investigation_id: UUID) -> list[AIOperationResponse]:
        try:
            records = await self._client.request(
                "GET",
                "/ai_operations",
                params={
                    "select": "*",
                    "investigation_id": f"eq.{investigation_id}",
                    "order": "started_at.asc",
                },
            )
            return [AIOperationResponse.model_validate(item) for item in records]
        except (StorageError, ValidationError) as exc:
            raise RepositoryError("Unable to retrieve investigation metrics") from exc


def aggregate_investigation_metrics(
    investigation_id: UUID,
    operations: list[AIOperationResponse],
) -> InvestigationMetricsResponse:
    durations: dict[AIOperationType, list[int]] = defaultdict(list)
    for operation in operations:
        durations[operation.operation_type].append(operation.duration_ms)
    latency = [
        LatencyMetric(
            operation_type=operation_type,
            call_count=len(values),
            total_duration_ms=sum(values),
            average_duration_ms=sum(values) / len(values),
        )
        for operation_type, values in durations.items()
    ]
    token_operations = [item for item in operations if item.total_tokens is not None]
    costs = [item.estimated_cost_usd for item in operations if item.estimated_cost_usd is not None]
    return InvestigationMetricsResponse(
        investigation_id=investigation_id,
        trace_ids=list(dict.fromkeys(item.trace_id for item in operations)),
        operations=operations,
        latency=latency,
        input_tokens=(
            sum(item.input_tokens or 0 for item in token_operations) if token_operations else None
        ),
        output_tokens=(
            sum(item.output_tokens or 0 for item in token_operations) if token_operations else None
        ),
        total_tokens=(
            sum(item.total_tokens or 0 for item in token_operations) if token_operations else None
        ),
        estimated_cost_usd=sum(costs) if costs else None,
        cost_status="estimated" if costs else "unknown_unconfigured",
        fallback_used=any(item.fallback_used for item in operations),
        serving_providers=sorted({item.provider for item in operations if item.provider}),
        serving_models=sorted({item.model for item in operations if item.model}),
    )
