import hashlib
import json
from pathlib import Path

from pydantic import TypeAdapter

from app.evaluation.models import IncidentEvaluationScenario

ROOT = Path(__file__).parents[3]


def test_holdout_is_valid_unseen_dataset_and_hash_matches_manifest() -> None:
    dataset = ROOT / "evaluation" / "incident_holdout.json"
    manifest = json.loads(
        (ROOT / "evaluation" / "incident_holdout_manifest.json").read_text(encoding="utf-8")
    )
    scenarios = TypeAdapter(list[IncidentEvaluationScenario]).validate_json(dataset.read_bytes())

    assert 5 <= len(scenarios) <= 8
    assert len({scenario.id for scenario in scenarios}) == len(scenarios)
    assert manifest["status"] == "frozen_before_official_run"
    assert manifest["scenario_count"] == len(scenarios)
    assert manifest["sha256"]["dataset"] == hashlib.sha256(dataset.read_bytes()).hexdigest()
