import json
from pathlib import Path

import pytest

from verified_data_factory.quality.export import build_golden_record_id
from verified_data_factory.quality.review_package import (
    append_review_decision,
    export_review_evidence,
    freeze_review_package,
    review_status,
)


def _source(tmp_path: Path) -> Path:
    path = tmp_path / "golden.jsonl"
    row = {
        "candidate_id": "candidate-a",
        "task": {},
        "instruction": "Find completed revenue by region.",
        "schema": [{"name": "orders", "columns": []}],
        "candidate_solution": "SELECT region, SUM(amount) FROM orders GROUP BY region",
        "fixture": {"edge_cases": ["zero_values"]},
        "verification": {
            "verdict": "PASS",
            "verification_strength": "STRONG",
            "oracle": {
                "expected": {"columns": ["region", "revenue"], "rows": []},
                "strategy": "private",
            },
            "mutation": {"mutation_score": 1.0},
        },
        "quality": {"family": "aggregation", "difficulty": 3, "decision": "GOLDEN"},
    }
    row["record_id"] = build_golden_record_id(
        task=row["task"],
        instruction=row["instruction"],
        schema=row["schema"],
        candidate_solution=row["candidate_solution"],
    )
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    return path


def _record_id(path: Path) -> str:
    return json.loads(path.read_text(encoding="utf-8"))["record_id"]


def _decide(package: Path, reviewer: str, slot: str, verdict: str) -> None:
    record_id = next(
        iter(json.loads((package / "manifest.json").read_text(encoding="utf-8"))["item_hashes"])
    )
    append_review_decision(
        package,
        record_id=record_id,
        reviewer_id=reviewer,
        slot=slot,
        verdict=verdict,
        reason="Checked intent and output",
        rubric_version="sql-review-v1",
    )


def test_decisions_survive_calls_and_require_independence(tmp_path: Path) -> None:
    package = tmp_path / "review"
    source = _source(tmp_path)
    freeze_review_package(source, package)
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_class"] == "DIAGNOSTIC"
    record_id = _record_id(source)
    assert review_status(package)["status_by_record"][record_id] == "PENDING"
    _decide(package, "reviewer-1", "first", "PASS")
    with pytest.raises(ValueError, match="distinct reviewer"):
        _decide(package, "reviewer-1", "second", "PASS")
    _decide(package, "reviewer-2", "second", "PASS")
    assert review_status(package)["status_by_record"][record_id] == "PASS"
    assert review_status(package)["decisions"] == 2
    derived = export_review_evidence(package, tmp_path / "golden.jsonl", tmp_path / "derived")
    assert derived["row_count"] == 1
    qualities = json.loads((tmp_path / "derived/qualities.json").read_text(encoding="utf-8"))
    assert qualities[0]["auditor_result"] == "PASS"
    with pytest.raises(ValueError, match="already has a decision"):
        _decide(package, "reviewer-3", "second", "FAIL")


def test_disagreement_requires_third_reviewer(tmp_path: Path) -> None:
    package = tmp_path / "review"
    source = _source(tmp_path)
    freeze_review_package(source, package)
    record_id = _record_id(source)
    _decide(package, "reviewer-1", "first", "PASS")
    _decide(package, "reviewer-2", "second", "FAIL")
    assert review_status(package)["status_by_record"][record_id] == "ADJUDICATION_REQUIRED"
    with pytest.raises(ValueError, match="distinct reviewer"):
        _decide(package, "reviewer-1", "adjudicator", "PASS")
    _decide(package, "reviewer-3", "adjudicator", "FAIL")
    assert review_status(package)["status_by_record"][record_id] == "FAIL"
    with pytest.raises(ValueError, match="final PASS"):
        export_review_evidence(package, tmp_path / "golden.jsonl", tmp_path / "derived")


def test_package_and_journal_tampering_fail_closed(tmp_path: Path) -> None:
    package = tmp_path / "review"
    freeze_review_package(_source(tmp_path), package)
    with pytest.raises(ValueError, match="already exists"):
        freeze_review_package(_source(tmp_path), package)
    _decide(package, "reviewer-1", "first", "PASS")
    journal = package / "decisions.jsonl"
    journal.write_text(
        journal.read_text(encoding="utf-8").replace("PASS", "FAIL"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="hash chain mismatch"):
        review_status(package)


def test_freeze_rejects_unqualified_or_forged_source(tmp_path: Path) -> None:
    source = _source(tmp_path)
    row = json.loads(source.read_text(encoding="utf-8"))
    row["verification"]["mutation"]["mutation_score"] = 0.5
    source.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="premium automated qualification"):
        freeze_review_package(source, tmp_path / "weak-package")
    row["verification"]["mutation"]["mutation_score"] = 1.0
    row["instruction"] = "Changed question"
    source.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not content-bound"):
        freeze_review_package(source, tmp_path / "forged-package")


def test_premium_freeze_rejects_undersized_pool_before_creating_package(tmp_path: Path) -> None:
    source = _source(tmp_path)
    target = tmp_path / "premium-package"
    with pytest.raises(ValueError, match="premium pre-review gates failed: row_count"):
        freeze_review_package(source, target, premium=True)
    assert not target.exists()


def test_duplicate_item_lines_fail_closed(tmp_path: Path) -> None:
    package = tmp_path / "review"
    freeze_review_package(_source(tmp_path), package)
    items = package / "items.jsonl"
    items.write_text(items.read_text(encoding="utf-8") * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate review item"):
        review_status(package)


def test_whitespace_cannot_create_a_second_identity(tmp_path: Path) -> None:
    package = tmp_path / "review"
    freeze_review_package(_source(tmp_path), package)
    _decide(package, "reviewer-1", "first", "PASS")
    with pytest.raises(ValueError, match="distinct reviewer"):
        _decide(package, " reviewer-1 ", "second", "PASS")
