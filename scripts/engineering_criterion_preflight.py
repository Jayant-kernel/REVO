"""Replay criterion producers without altering receipt-bound audit preflight."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import engineering_discrimination_measurement as discrimination
from scripts import engineering_rule_measurement as rules
from scripts.engineering_metric_preflight import validate_metric as validate_audit_metric
from verified_data_factory.verification.receipt_models import ArtifactRef
from verified_data_factory.verification.receipt_validation import artifact


def validate_metric(root: Path, reference: dict[str, Any], metric: str) -> int:
    data = json.loads(artifact(root, ArtifactRef.model_validate(reference)).read_text())
    producer = data.get("producer")
    if producer not in {rules.PRODUCER, discrimination.PRODUCER}:
        return validate_audit_metric(root, reference, metric)
    if data.get("rubric_version") != "engineering-1.0":
        raise ValueError("unsupported measurement rubric version")
    if producer == rules.PRODUCER:
        if metric != rules.METRIC or data.get("criterion") != "correctness.contract_rules":
            raise ValueError("unsupported metric for rule measurement producer")
        return rules.validate(root, reference)
    if metric not in discrimination.METRICS.values():
        raise ValueError("unsupported metric for discrimination measurement producer")
    return discrimination.validate(root, reference)[metric]
