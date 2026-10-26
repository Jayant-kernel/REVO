"""Validate current full-population measurements before invoking the frozen scorer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.engineering_program_audit import audit, population
from verified_data_factory.verification.receipt_models import ArtifactRef
from verified_data_factory.verification.receipt_validation import artifact, encode, runtime_identity


def validate_metric(root: Path, reference: dict[str, Any], metric: str) -> int:
    data = json.loads(artifact(root, ArtifactRef.model_validate(reference)).read_text())
    expected = [{"contract_id": name, "contract_version": version} for name, version in population()]
    if (encode(data.get("population")) != encode(expected)
            or type(data.get("population_count")) is not int or data["population_count"] != len(expected)):
        raise ValueError("partial, duplicated or stale population cannot represent the full catalog")
    if data.get("producer") != "scripts/engineering_program_audit.py" or data.get("runtime") != runtime_identity():
        raise ValueError("unsupported metric producer or stale runtime")
    for relative, checksum in data.get("source_hashes", {}).items():
        artifact(root, ArtifactRef(path=relative, sha256=checksum))
    fresh = audit(root)
    if data.get("source_hashes") != fresh["source_hashes"] or metric not in fresh["metrics"]:
        raise ValueError("unsupported measurement or incomplete dependency closure")
    value = data.get("metrics", {}).get(metric)
    if type(value) is not int or value != fresh["metrics"][metric]:
        raise ValueError("metric differs from current executed catalog reconciliation")
    return int(fresh["metrics"][metric])
