import asyncio
import json
from collections.abc import Awaitable
from pathlib import Path

from pydantic import TypeAdapter

from app.evaluation.harness import evaluate_incidents
from app.evaluation.models import IncidentEvaluationScenario
from app.schemas.llm import ChatMessage, ModelToolCall, ModelTurn, ToolDefinition


async def _await_value[T](value: Awaitable[T]) -> T:
    return await value


def run_async[T](value: Awaitable[T]) -> T:
    return asyncio.run(_await_value(value))


def load_scenarios() -> list[IncidentEvaluationScenario]:
    path = Path(__file__).parents[3] / "evaluation" / "incident_benchmark.json"
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    return TypeAdapter(list[IncidentEvaluationScenario]).validate_python(raw)


class EvidenceGroundedEvaluationLLM:
    provider_name = "deterministic-test"
    model_name = "deterministic-test-model"

    def __init__(self) -> None:
        self.calls = 0

    async def complete(
        self,
        messages: list[ChatMessage],
        _tools: list[ToolDefinition],
    ) -> ModelTurn:
        self.calls += 1
        if self.calls == 1:
            return ModelTurn(
                tool_calls=[
                    ModelToolCall(
                        id="commit-search",
                        name="list_recent_commits",
                        arguments='{"limit":5}',
                    ),
                    ModelToolCall(
                        id="knowledge-search",
                        name="search_knowledge",
                        arguments='{"query":"deployment write failures schema","top_k":5}',
                    ),
                ]
            )
        tool_messages = [message for message in messages if message.role == "tool"]
        evidence = [
            item
            for message in tool_messages
            for item in json.loads(message.content or "{}")["evidence"]
        ]
        culprit = next(item for item in evidence if item["source_type"] == "github_commit")
        return ModelTurn(
            content=json.dumps(
                {
                    "summary": "The release uses a database field whose migration was omitted.",
                    "confidence": 0.88,
                    "suspected_change": "Application and deployed schema are out of sync.",
                    "suspected_culprit_id": culprit["source_reference"],
                    "supporting_evidence_ids": [item["evidence_id"] for item in evidence],
                    "missing_information": ["Production migration history"],
                    "recommended_next_steps": ["Apply or roll back the migration-dependent code"],
                }
            )
        )


def test_fixed_incident_dataset_is_transparent_and_has_ten_scenarios() -> None:
    scenarios = load_scenarios()

    assert len(scenarios) == 10
    assert len({scenario.id for scenario in scenarios}) == 10
    assert all(
        scenario.expected_culprit_id not in scenario.incident.title for scenario in scenarios
    )
    assert all(
        scenario.expected_culprit_id in {item.source_reference for item in scenario.evidence}
        for scenario in scenarios
    )


def test_incident_evaluation_uses_real_orchestration_and_deterministic_metrics() -> None:
    scenario = load_scenarios()[0]
    report = run_async(evaluate_incidents([scenario], EvidenceGroundedEvaluationLLM()))

    assert report.metrics.completion_rate == 1.0
    assert report.metrics.culprit_accuracy == 1.0
    assert report.metrics.citation_precision == 1.0
    assert report.metrics.citation_recall == 1.0
    assert report.metrics.invalid_citation_rate == 0.0
    assert report.metrics.average_tool_calls == 2.0
    assert report.metrics.average_confidence_correct == 0.88
    assert report.metrics.average_confidence_incorrect is None
    assert report.scenarios[0].called_tools == ["list_recent_commits", "search_knowledge"]
