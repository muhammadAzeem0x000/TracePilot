"""Run the fixed incident-diagnosis benchmark with the configured live LLM."""

import argparse
import asyncio
import json
from pathlib import Path

from pydantic import TypeAdapter

from app.ai.provider import OpenAICompatibleLLMProvider
from app.config.settings import Settings
from app.evaluation.harness import evaluate_incidents
from app.evaluation.models import IncidentEvaluationReport, IncidentEvaluationScenario


def markdown_report(report: IncidentEvaluationReport) -> str:
    metrics = report.metrics
    lines = [
        "# TracePilot Incident Evaluation",
        "",
        f"Prompt: `{report.prompt_version}`  ",
        f"Model: `{report.model_name}`  ",
        "Confidence is model-reported and is not a calibrated probability.",
        "",
        "## Aggregate metrics",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Completion rate | {metrics.completion_rate:.3f} |",
        f"| Culprit accuracy | {metrics.culprit_accuracy:.3f} |",
        f"| Citation precision | {metrics.citation_precision:.3f} |",
        f"| Citation recall | {metrics.citation_recall:.3f} |",
        f"| Invalid citation rate | {metrics.invalid_citation_rate:.3f} |",
        f"| Average tool calls | {metrics.average_tool_calls:.2f} |",
        f"| Average latency | {metrics.average_latency_ms:.1f} ms |",
        f"| Average confidence | {_optional(metrics.average_confidence)} |",
        f"| Confidence when correct | {_optional(metrics.average_confidence_correct)} |",
        f"| Confidence when incorrect | {_optional(metrics.average_confidence_incorrect)} |",
        f"| High-confidence incorrect | {metrics.high_confidence_incorrect_count} |",
        f"| Completed / failed | {metrics.completed_count} / {metrics.failed_count} |",
        "",
        "## Scenario results",
        "",
        "| Scenario | Completed | Correct | Citation P/R | Confidence | Tools | "
        "Latency ms | Failure class |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in report.scenarios:
        lines.append(
            f"| {item.scenario_id} | {item.completed} | {item.culprit_correct} | "
            f"{item.citation_precision:.2f}/{item.citation_recall:.2f} | "
            f"{_optional(item.confidence)} | {item.tool_calls} | {item.latency_ms:.1f} | "
            f"{item.failure_class.value if item.failure_class else '—'} |"
        )
    lines.extend(["", "## Preserved details", ""])
    for item in report.scenarios:
        lines.extend(
            [
                f"### {item.scenario_id}",
                "",
                f"- Expected: `{item.expected_culprit_id}`",
                f"- Predicted: `{item.predicted_culprit_id}`",
                f"- Called tools: {', '.join(item.called_tools) or 'none'}",
                f"- Cited sources: {', '.join(item.cited_source_references) or 'none'}",
                f"- Failure: {item.failure_reason or 'none'}",
                "",
            ]
        )
    return "\n".join(lines)


def _optional(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


async def run(benchmark_path: Path) -> IncidentEvaluationReport:
    content = await asyncio.to_thread(benchmark_path.read_text, encoding="utf-8")
    raw: object = json.loads(content)
    scenarios = TypeAdapter(list[IncidentEvaluationScenario]).validate_python(raw)
    settings = Settings()
    base_url, api_key, model = settings.require_llm()
    provider = OpenAICompatibleLLMProvider(base_url, api_key, model)
    return await evaluate_incidents(scenarios, provider)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("evaluation/incident_benchmark.json"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("docs/evaluation"))
    arguments = parser.parse_args()
    report = asyncio.run(run(arguments.benchmark))
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = arguments.output_dir / "incident_evaluation.json"
    markdown_path = arguments.output_dir / "incident_evaluation.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(markdown_report(report), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(markdown_path)}, indent=2))


if __name__ == "__main__":
    main()
