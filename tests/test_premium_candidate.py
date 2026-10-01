"""The premium screen must fail honestly on an undersized diagnostic pool."""

from __future__ import annotations

import json
from pathlib import Path

from tests.test_review_package import _source
from verified_data_factory.cli import main
from verified_data_factory.quality.premium_candidate import assess_premium_candidate


def test_diagnostic_golden_is_not_a_premium_review_candidate(tmp_path: Path) -> None:
    source = _source(tmp_path)
    report = assess_premium_candidate(source)
    assert report["automated_pre_review_gates_pass"] is False
    assert report["gates"]["row_count"] == {"actual": 1, "target": 80, "passed": False}
    assert report["gates"]["edge_coverage"]["target"] == "at least 15 of 17"
    assert report["gates"]["automated_row_evidence"]["passed"] is False
    assert "external benchmark contamination" in report["not_measured"]
    assert "normalized SQL AST and semantic equivalence" in report["not_measured"]


def test_premium_check_cli_returns_failure_without_modifying_source(tmp_path: Path) -> None:
    source = _source(tmp_path)
    original = source.read_bytes()
    report_path = tmp_path / "premium-report.json"
    assert (
        main(["quality", "premium-check", "--golden", str(source), "--output", str(report_path)])
        == 1
    )
    assert source.read_bytes() == original
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["gates"]["family_balance"]["passed"] is False
    assert report["gates"]["schema_variety"]["passed"] is False


def test_candidate_sibling_flag_is_reported_separately_from_unresolved_overlap(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)
    row = json.loads(source.read_text(encoding="utf-8").strip())
    row["quality"]["contamination_flags"] = [
        {
            "flag_type": "EXACT_OVERLAP", "detail": "same task as sibling",
            "hard": False, "scope": "SAME_TASK_SIBLINGS",
        }
    ]
    source.write_text(json.dumps(row) + "\n", encoding="utf-8")
    report = assess_premium_candidate(source)
    assert report["candidate_sibling_exact_overlap_flags"] == 1
    assert report["gates"]["unresolved_contamination_flags"]["actual"] == 0

    row["quality"]["contamination_flags"][0].pop("scope")
    source.write_text(json.dumps(row) + "\n", encoding="utf-8")
    old_report = assess_premium_candidate(source)
    assert old_report["gates"]["unresolved_contamination_flags"]["actual"] == 1
