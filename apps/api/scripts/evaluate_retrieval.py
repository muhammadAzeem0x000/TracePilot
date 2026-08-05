"""Run the fixed retrieval benchmark and save JSON plus Markdown reports."""

import argparse
import asyncio
import json
from pathlib import Path

from pydantic import TypeAdapter

from app.config.settings import Settings
from app.retrieval.evaluation import (
    RetrievalBenchmarkCase,
    RetrievalEvaluationReport,
    evaluate_method,
)
from app.retrieval.factory import build_retrieval_service
from app.schemas.knowledge import KnowledgeSearchMode


async def evaluate(
    repository_full_name: str,
    cases: list[RetrievalBenchmarkCase],
) -> RetrievalEvaluationReport:
    service = build_retrieval_service(Settings())
    methods = [
        await evaluate_method(service, repository_full_name, cases, mode)
        for mode in KnowledgeSearchMode
    ]
    return RetrievalEvaluationReport(repository_full_name=repository_full_name, methods=methods)


def markdown_report(report: RetrievalEvaluationReport) -> str:
    lines = [
        "# TracePilot Retrieval Evaluation",
        "",
        f"Repository scope: `{report.repository_full_name}`",
        "",
        "| Method | Hit@1 | Hit@3 | Hit@5 | MRR | Avg latency (ms) |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method in report.methods:
        lines.append(
            f"| {method.mode.value} | {method.source_hit_at_1:.3f} | "
            f"{method.source_hit_at_3:.3f} | {method.source_hit_at_5:.3f} | "
            f"{method.mrr:.3f} | {method.average_latency_ms:.1f} |"
        )
    lines.extend(["", "## Per-query results", ""])
    for method in report.methods:
        lines.extend([f"### {method.mode.value}", ""])
        for case in method.cases:
            lines.append(
                f"- `{case.query}` — RR {case.reciprocal_rank:.3f}; "
                f"top sources: {', '.join(case.retrieved_sources)}"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path("knowledge/retrieval_benchmark.json"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("docs/evaluation"))
    arguments = parser.parse_args()
    raw: object = json.loads(arguments.benchmark.read_text(encoding="utf-8"))
    cases = TypeAdapter(list[RetrievalBenchmarkCase]).validate_python(raw)
    report = asyncio.run(evaluate(arguments.repository, cases))
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = arguments.output_dir / "retrieval_evaluation.json"
    markdown_path = arguments.output_dir / "retrieval_evaluation.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    markdown_path.write_text(markdown_report(report), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(markdown_path)}, indent=2))


if __name__ == "__main__":
    main()
