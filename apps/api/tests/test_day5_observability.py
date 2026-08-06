import asyncio
from collections.abc import Awaitable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai.provider import (
    FallbackLLMProvider,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMUnavailableError,
)
from app.api.dependencies import get_incident_repository
from app.config.settings import Settings, get_settings
from app.main import app
from app.observability.pricing import PricingRegistry
from app.observability.providers import ObservedLLMProvider
from app.observability.tracing import begin_trace, end_trace
from app.repositories.incidents import IncidentRepository
from app.repositories.operations import aggregate_investigation_metrics
from app.schemas.llm import ChatMessage, ModelTurn, ToolDefinition
from app.schemas.operations import AIOperationCreate, AIOperationResponse
from tests.conftest import FakeIncidentRepository


def run_async[T](awaitable: Awaitable[T]) -> T:
    async def wait() -> T:
        return await awaitable

    return asyncio.run(wait())


class StubProvider:
    def __init__(self, outcome: ModelTurn | Exception, name: str = "primary") -> None:
        self.outcome = outcome
        self.provider_name = name
        self.model_name = f"{name}-model"
        self.calls = 0

    async def complete(
        self,
        _messages: list[ChatMessage],
        _tools: list[ToolDefinition],
    ) -> ModelTurn:
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class MemoryOperationRepository:
    def __init__(self) -> None:
        self.items: list[AIOperationResponse] = []

    async def create(self, operation: AIOperationCreate) -> AIOperationResponse:
        stored = AIOperationResponse(
            id=uuid4(),
            created_at=datetime.now(UTC),
            **operation.model_dump(),
        )
        self.items.append(stored)
        return stored

    async def list_for_investigation(self, investigation_id: UUID) -> list[AIOperationResponse]:
        return [item for item in self.items if item.investigation_id == investigation_id]


def test_fallback_uses_secondary_only_for_transient_failures() -> None:
    primary = StubProvider(LLMRateLimitError("limited"))
    fallback = StubProvider(
        ModelTurn(
            content="{}",
            provider="secondary",
            model="secondary-model",
            input_tokens=10,
            output_tokens=4,
            total_tokens=14,
        ),
        "secondary",
    )

    turn = run_async(FallbackLLMProvider(primary, fallback).complete([], []))

    assert turn.fallback_used is True
    assert turn.fallback_reason == "LLMRateLimitError"
    assert turn.provider == "secondary"
    assert fallback.calls == 1


def test_fallback_does_not_mask_authentication_failure() -> None:
    primary = StubProvider(LLMAuthenticationError("bad key"))
    fallback = StubProvider(ModelTurn(content="{}"), "secondary")

    with pytest.raises(LLMAuthenticationError):
        run_async(FallbackLLMProvider(primary, fallback).complete([], []))

    assert fallback.calls == 0


@pytest.mark.parametrize("error", [LLMUnavailableError("down"), LLMRateLimitError("limited")])
def test_transient_failure_classes_are_fallback_eligible(error: Exception) -> None:
    fallback = StubProvider(ModelTurn(content="{}"), "secondary")
    turn = run_async(FallbackLLMProvider(StubProvider(error), fallback).complete([], []))
    assert turn.fallback_used is True


def test_observed_provider_records_reported_tokens_and_configured_cost() -> None:
    operations = MemoryOperationRepository()
    provider = StubProvider(
        ModelTurn(
            content="{}",
            provider="primary",
            model="primary-model",
            input_tokens=1_000,
            output_tokens=500,
            total_tokens=1_500,
        )
    )
    pricing = PricingRegistry.from_json(
        '{"primary-model":{"input_usd_per_million_tokens":1,"output_usd_per_million_tokens":2}}',
        "2026-08-06",
    )
    observed = ObservedLLMProvider(provider, operations, pricing)
    investigation_id = uuid4()
    token = begin_trace(investigation_id)
    try:
        run_async(observed.complete([], []))
    finally:
        end_trace(token)

    operation = operations.items[0]
    assert operation.input_tokens == 1_000
    assert operation.output_tokens == 500
    assert operation.total_tokens == 1_500
    assert operation.estimated_cost_usd == pytest.approx(0.002)
    assert operation.metadata["pricing_source_date"] == "2026-08-06"


def test_unknown_pricing_and_missing_usage_never_invent_cost_or_tokens() -> None:
    operations = MemoryOperationRepository()
    provider = StubProvider(ModelTurn(content="{}", model="unknown-model"))
    observed = ObservedLLMProvider(provider, operations, PricingRegistry.from_json(None, None))
    token = begin_trace(uuid4())
    try:
        run_async(observed.complete([], []))
    finally:
        end_trace(token)

    operation = operations.items[0]
    assert operation.total_tokens is None
    assert operation.estimated_cost_usd is None


def test_metrics_aggregate_provider_usage_without_double_counting_unknowns() -> None:
    repository = MemoryOperationRepository()
    investigation_id = uuid4()
    token = begin_trace(investigation_id)
    try:
        observed = ObservedLLMProvider(
            StubProvider(ModelTurn(content="{}", input_tokens=3, output_tokens=2, total_tokens=5)),
            repository,
            PricingRegistry.from_json(None, None),
        )
        run_async(observed.complete([], []))
    finally:
        end_trace(token)

    metrics = aggregate_investigation_metrics(investigation_id, repository.items)
    assert metrics.total_tokens == 5
    assert metrics.estimated_cost_usd is None
    assert metrics.cost_status == "unknown_unconfigured"
    assert metrics.latency[0].call_count == 1


def test_production_configuration_rejects_wildcard_and_unprotected_writes() -> None:
    with pytest.raises(ValidationError, match="wildcard"):
        Settings(
            _env_file=None,
            app_environment="production",
            public_demo_mode=True,
            supabase_url="https://example.supabase.co",
            supabase_key="secret",
            cors_origins="*",
        )
    with pytest.raises(ValidationError, match="PUBLIC_DEMO_MODE"):
        Settings(
            _env_file=None,
            app_environment="production",
            supabase_url="https://example.supabase.co",
            supabase_key="secret",
            cors_origins="https://tracepilot.example",
        )


def test_public_demo_blocks_create_incident_server_side() -> None:
    repository = FakeIncidentRepository()

    def override_repository() -> IncidentRepository:
        return repository

    def override_settings() -> Settings:
        return Settings(_env_file=None, public_demo_mode=True)

    app.dependency_overrides[get_incident_repository] = override_repository
    app.dependency_overrides[get_settings] = override_settings
    try:
        with TestClient(app) as client:
            config = client.get("/api/v1/config")
            response = client.post(
                "/api/v1/incidents",
                json={
                    "title": "Blocked demo mutation",
                    "description": "This must not be persisted.",
                    "severity": "low",
                    "started_at": "2026-08-06T10:00:00Z",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert config.json() == {"public_demo_mode": True, "mutations_enabled": False}
    assert response.status_code == 403
    assert repository.incidents == {}


def test_ai_operations_migration_is_service_role_only() -> None:
    migration = (
        Path(__file__).parents[3]
        / "supabase"
        / "migrations"
        / "20260806113455_day5_ai_observability.sql"
    ).read_text(encoding="utf-8")
    assert "enable row level security" in migration
    assert "revoke all on table public.ai_operations from public, anon, authenticated" in migration
    assert "grant select, insert on table public.ai_operations to service_role" in migration
    assert "raw_prompt" not in migration
    assert "evidence_body" not in migration
