"""Missing populations and abstentions cannot turn into perfect checker metrics."""
from copy import deepcopy

import pytest

from scripts import engineering_checker_comparison as checker
from scripts.engineering_checker_comparison import classify, summarize


def test_comparison_denominators_and_abstentions_are_explicit():
    rows = [{"id": "correct", "family": "f", "label": "correct", "infra_failure": False,
             "invalid_initial_sql": False, "wall_seconds": 1,
             "decisions": {"execution_only": "accept", "ordinary_fixture": "accept", "full_verifier": "abstain"}},
            {"id": "wrong", "family": "f", "label": "wrong", "infra_failure": False,
             "invalid_initial_sql": False, "wall_seconds": 1,
             "decisions": {"execution_only": "accept", "ordinary_fixture": "accept", "full_verifier": "reject"}}]
    report = summarize(rows, 2)["overall"]
    assert report["population"] == 2
    assert report["checkers"]["execution_only"]["false_acceptance"] == 1
    assert report["checkers"]["full_verifier"] == {"abstention": 1, "true_rejection": 1}
    for cases, population in (([], 0), (rows[:1], 2), ([rows[0], rows[0]], 2)):
        with pytest.raises(ValueError, match="population"):
            summarize(cases, population)
    with pytest.raises(ValueError):
        classify("unknown", "reject")


def test_protocol_rejects_relabelled_and_stale_populations(tmp_path):
    import json

    path = tmp_path / "protocol.json"
    checker.freeze(path)
    original = json.loads(path.read_text(encoding="utf-8"))
    checker.validate_protocol(original)
    tampered = deepcopy(original)
    tampered["cases"][0]["label"] = "wrong"
    with pytest.raises(ValueError, match="substituted"):
        checker.validate_protocol(tampered)
    missing = deepcopy(original)
    missing["source_hashes"] = {}
    with pytest.raises(ValueError, match="dependency"):
        checker.validate_protocol(missing)
