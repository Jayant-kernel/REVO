"""Phase 6 coverage-aware SaaS v2 fuzzing remains executable and non-vacuous."""

from __future__ import annotations

import json
from pathlib import Path

from scratch.funnel_experiment.evidence.run_phase6_saas_v2_fuzz import BEHAVIORS, run

ROOT = Path(__file__).resolve().parents[1]


def test_phase6_fuzz_meets_committed_coverage_and_has_no_divergences(tmp_path: Path) -> None:
    output = tmp_path / "phase6-fuzz.json"
    report = run(
        ROOT / "scratch/funnel_experiment/evidence/phase6-saas-v2-fuzz-threshold.json", output
    )
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert report == persisted
    assert report["status"] == "PASS"
    assert report["divergences"] == []
    assert set(report["invalid_inputs_rejected"]) == {"duplicate_order_key", "inconsistent_group"}
    minimum = report["threshold"]["content"]["behavior_minimum_per_seed"]
    for counts in report["coverage"].values():
        assert set(counts) == set(BEHAVIORS)
        assert all(count >= minimum for count in counts.values())
