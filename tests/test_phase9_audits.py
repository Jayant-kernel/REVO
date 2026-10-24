"""Phase 9 audits remain read-only, narrow, and reproducible."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.package_a_phase9_audit import generic_oracle_blast_radius, run

ROOT = Path(__file__).resolve().parents[1]


def test_generic_oracle_allowlist_is_exact_and_audit_only() -> None:
    report = generic_oracle_blast_radius(ROOT / "configs/package_a/generic_oracle_allowlist.json")
    assert report["status"] == "PASS"
    assert report["allowlist_match"] is True
    assert len(report["audit_required"]) == 17


def test_phase9_audit_writes_three_seed_vacuity_csvs_without_mutating_paused_run(tmp_path: Path) -> None:
    baseline = (ROOT / "scratch/paused-run.baseline.sha256.txt").read_bytes()
    report = run(ROOT, tmp_path)
    assert report["status"] == "PASS"
    assert report["paused_golden_overlap"]["status"] == "MEASURED_NOT_QUALIFIED"
    assert report["diversity_measurements"]["status"] == "MEASURED_NOT_QUALIFIED"
    assert (ROOT / "scratch/paused-run.baseline.sha256.txt").read_bytes() == baseline
    assert json.loads((tmp_path / "phase9-audit.json").read_text(encoding="utf-8")) == report
    for name in report["three_seed_vacuity_csvs"]:
        with (tmp_path / name).open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows
        assert {row["vacuity"] for row in rows} <= {"VACUOUS", "NON_VACUOUS"}
