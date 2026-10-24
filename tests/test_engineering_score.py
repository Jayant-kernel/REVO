import json
from pathlib import Path

import pytest

from scripts.engineering_score import check_lock, digest, receipt_metric


def test_missing_evidence_never_earns_credit(tmp_path):
    assert receipt_metric(tmp_path, {}, "failures")[0] is None


@pytest.mark.parametrize("population,checks,failures", [(0, 1, 0), (1, 0, 0), (1, 1, 1)])
def test_empty_or_failed_receipts_are_rejected(tmp_path, population, checks, failures):
    source = tmp_path / "source.txt"
    source.write_text("source")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"evidence_id": "e", "producer": "p", "population_count": population,
                                  "checks_run": checks, "execution_failures": failures,
                                  "source_hashes": {"source.txt": digest(source)}, "metrics": {"failures": 0}}))
    assert receipt_metric(tmp_path, {"path": "receipt.json", "sha256": digest(receipt)}, "failures")[0] is None


def test_dependency_edits_invalidate_receipt(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"evidence_id": "e", "producer": "p", "population_count": 1,
                                  "checks_run": 1, "execution_failures": 0,
                                  "source_hashes": {"source.txt": digest(source)}, "metrics": {"failures": 0}}))
    reference = {"path": "receipt.json", "sha256": digest(receipt)}
    assert receipt_metric(tmp_path, reference, "failures")[0] == 0
    source.write_text("changed")
    assert receipt_metric(tmp_path, reference, "failures")[0] is None


def test_frozen_measurement_edits_are_rejected(tmp_path):
    source = tmp_path / "scorer.py"
    source.write_text("original")
    lock = {"measurement_sources": {"scorer.py": digest(source)}}
    check_lock(tmp_path, lock)
    source.write_text("changed")
    with pytest.raises(ValueError):
        check_lock(tmp_path, lock)


def test_weights_are_exactly_one_hundred():
    rubric = json.loads(Path("configs/package_a/engineering-rubric.json").read_text())
    assert sum(d["weight"] for d in rubric["dimensions"]) == 100
    assert all(sum(c["points"] for c in d["criteria"]) == d["weight"] for d in rubric["dimensions"])
