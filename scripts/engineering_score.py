"""Frozen fail-closed engineering-score arithmetic; run scoring only in phase 11."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receipt_metric(root: Path, reference: dict[str, Any], metric: str) -> tuple[float | None, str]:
    try:
        path = (root / reference["path"]).resolve()
        if not path.is_relative_to(root.resolve()) or digest(path) != reference["sha256"]:
            return None, "artifact missing, outside workspace or stale"
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if not receipt.get("evidence_id") or not receipt.get("producer"):
            return None, "missing evidence identity/producer"
        if receipt.get("population_count", 0) < 1 or receipt.get("checks_run", 0) < 1:
            return None, "empty population or unexecuted checks"
        if receipt.get("execution_failures") != 0:
            return None, "failed or missing execution outcome"
        sources = receipt.get("source_hashes", {})
        if not sources:
            return None, "missing dependency hashes"
        for relative, expected in sources.items():
            source = (root / relative).resolve()
            if not source.is_relative_to(root.resolve()) or digest(source) != expected:
                return None, "stale dependency"
        value = receipt["metrics"][metric]
        if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
            return None, "invalid metric"
        return value, "fresh executed metric"
    except (OSError, KeyError, ValueError, TypeError):
        return None, "missing or malformed receipt"


def score(root: Path, rubric: dict[str, Any], references: dict[str, Any]) -> dict[str, Any]:
    dimensions = []
    for dimension in rubric["dimensions"]:
        criteria = []
        for criterion in dimension["criteria"]:
            value, reason = receipt_metric(root, references.get(criterion["metric"], {}), criterion["metric"])
            passed = value is not None and value <= criterion["max"]
            criteria.append({"id": criterion["id"], "metric": criterion["metric"],
                             "actual": value, "threshold": criterion["max"],
                             "points": criterion["points"] if passed else 0,
                             "reason": reason if passed else reason + "; no credit"})
        dimensions.append({"id": dimension["id"], "maximum": dimension["weight"],
                           "points": sum(c["points"] for c in criteria), "criteria": criteria})
    return {"rubric_version": rubric["version"], "official_historical_score": 52,
            "engineering_score": sum(d["points"] for d in dimensions),
            "dimensions": dimensions, "learning_value": "NOT MEASURED"}


def check_lock(root: Path, lock: dict[str, Any]) -> None:
    for relative, expected in lock["measurement_sources"].items():
        if digest(root / relative) != expected:
            raise ValueError(f"frozen measurement changed: {relative}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    lock = json.loads((root / "scratch/funnel_experiment/engineering/phase0-lock.json").read_text())
    check_lock(root, lock)
    rubric = json.loads((root / "configs/package_a/engineering-rubric.json").read_text())
    report = score(root, rubric, json.loads(args.input.read_text()))
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
