import json

import pytest

from scripts import engineering_criterion_preflight as preflight
from verified_data_factory.verification.receipt_validation import digest


@pytest.mark.parametrize("producer,metric,value", [
    (preflight.rules.PRODUCER, preflight.rules.METRIC, 784),
    *[(preflight.discrimination.PRODUCER, metric, 42)
      for metric in preflight.discrimination.METRICS.values()],
])
def test_criterion_preflight_uses_live_validator(tmp_path, monkeypatch, producer, metric, value):
    path = tmp_path / "measurement.json"
    path.write_text(json.dumps({"producer": producer, "rubric_version": "engineering-1.0",
                                "criterion": "correctness.contract_rules"}))
    reference = {"path": path.name, "sha256": digest(path)}
    calls = []

    def replay(root, ref):
        calls.append((root, ref))
        return value if producer == preflight.rules.PRODUCER else {metric: value}

    module = preflight.rules if producer == preflight.rules.PRODUCER else preflight.discrimination
    monkeypatch.setattr(module, "validate", replay)
    assert preflight.validate_metric(tmp_path, reference, metric) == value
    assert calls == [(tmp_path, reference)]

    def reject(root, ref):
        raise ValueError("stale dependency from live replay")

    monkeypatch.setattr(module, "validate", reject)
    with pytest.raises(ValueError, match="stale dependency from live replay"):
        preflight.validate_metric(tmp_path, reference, metric)


@pytest.mark.parametrize("producer,metric,rubric,criterion", [
    (preflight.rules.PRODUCER, "challenge_deficient_contracts", "engineering-1.0", "correctness.contract_rules"),
    (preflight.rules.PRODUCER, preflight.rules.METRIC, "engineering-999", "correctness.contract_rules"),
    (preflight.rules.PRODUCER, preflight.rules.METRIC, "engineering-1.0", "correctness.typed_comparator"),
    (preflight.discrimination.PRODUCER, preflight.rules.METRIC, "engineering-1.0", None),
    (preflight.discrimination.PRODUCER, "challenge_deficient_contracts", "engineering-999", None),
])
def test_criterion_preflight_rejects_wrong_metric_or_rubric(tmp_path, producer, metric, rubric, criterion):
    path = tmp_path / "measurement.json"
    path.write_text(json.dumps({"producer": producer, "rubric_version": rubric, "criterion": criterion}))
    with pytest.raises(ValueError, match="unsupported"):
        preflight.validate_metric(tmp_path, {"path": path.name, "sha256": digest(path)}, metric)


def test_unknown_producer_cannot_bypass_audit_validation(tmp_path):
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps({"producer": "invented", "population": [], "population_count": 57}))
    with pytest.raises(ValueError, match="partial, duplicated or stale population"):
        preflight.validate_metric(tmp_path, {"path": path.name, "sha256": digest(path)}, "challenge_deficient_contracts")
