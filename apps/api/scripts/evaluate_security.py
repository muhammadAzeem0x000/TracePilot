import json
from pathlib import Path

from app.security.evaluation import evaluate_adversarial_cases, load_cases

ROOT = Path(__file__).parents[3]


def main() -> None:
    cases = load_cases(ROOT / "evaluation" / "adversarial_security.json")
    frontend = (ROOT / "apps" / "web" / "src" / "app" / "page.tsx").read_text(encoding="utf-8")
    report = evaluate_adversarial_cases(cases, frontend_source=frontend)
    output_dir = ROOT / "docs" / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "adversarial_security.json"
    md_path = output_dir / "adversarial_security.md"
    json_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    rows = "\n".join(
        f"| {item.id} | {item.attack_type.value} | {'yes' if item.blocked else 'no'} | "
        f"{'yes' if item.unsafe_execution else 'no'} | {item.detail} |"
        for item in report.cases
    )
    metrics = report.metrics
    md_path.write_text(
        "# Adversarial security evaluation\n\n"
        "Deterministic suite version: `adversarial_v1`. No LLM judge is used.\n\n"
        "| Case | Boundary | Blocked | Unsafe execution | Result |\n"
        "|---|---|---:|---:|---|\n"
        f"{rows}\n\n"
        "## Metrics\n\n"
        f"- Scenarios: {metrics.scenario_count}\n"
        f"- Successful expected blocks: {metrics.successful_blocks}/{metrics.expected_blocks}\n"
        f"- Forbidden tool executions: {metrics.forbidden_tool_execution_count}\n"
        f"- Cross-repository accesses: {metrics.cross_repository_access_count}\n"
        f"- Invalid citations accepted: {metrics.invalid_citation_acceptance_count}\n"
        f"- Unsafe mutations: {metrics.unsafe_mutation_count}\n",
        encoding="utf-8",
    )
    print(json.dumps(report.metrics.model_dump(), indent=2))
    if any(item.unsafe_execution for item in report.cases):
        raise SystemExit("Unsafe execution detected")
    if metrics.successful_blocks != metrics.expected_blocks:
        raise SystemExit("An expected security boundary did not block the attack")


if __name__ == "__main__":
    main()
