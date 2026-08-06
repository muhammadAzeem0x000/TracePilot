import hashlib
import json
from pathlib import Path

from pydantic import TypeAdapter

from app.ai.prompts.investigation_v2 import PROMPT_VERSION
from app.evaluation.models import IncidentEvaluationScenario

ROOT = Path(__file__).parents[3]
DATASET = ROOT / "evaluation" / "incident_holdout.json"
MANIFEST = ROOT / "evaluation" / "incident_holdout_manifest.json"
FROZEN_FILES = {
    "dataset": DATASET,
    "investigation_prompt": ROOT / "apps/api/app/ai/prompts/investigation_v2.py",
    "rerank_prompt": ROOT / "apps/api/app/ai/prompts/rerank_v1.py",
    "tool_definitions": ROOT / "apps/api/app/ai/tool_definitions.py",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    scenarios = TypeAdapter(list[IncidentEvaluationScenario]).validate_json(DATASET.read_bytes())
    manifest = {
        "status": "frozen_before_official_run",
        "scenario_count": len(scenarios),
        "prompt_version": PROMPT_VERSION,
        "rerank_prompt_version": "rerank_v1",
        "max_tool_calls": 6,
        "final_output_retries": 1,
        "sha256": {name: sha256(path) for name, path in FROZEN_FILES.items()},
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
