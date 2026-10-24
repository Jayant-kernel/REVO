"""No empty, stale, altered or absent evidence becomes zero violations."""
from copy import deepcopy

import pytest

from scripts.engineering_rule_measurement import recompute

EXPECTED = [{"contract_id": "a", "contract_version": 1}, {"contract_id": "b", "contract_version": 2}]


def rows():
    return [{**EXPECTED[0], "declared_rules": ["objective", "schema:id"], "covered_rules": ["objective", "schema:id"], "evidence_status": "REPLAYED_CURRENT"},
            {**EXPECTED[1], "declared_rules": ["objective", "schema:id"], "covered_rules": [], "evidence_status": "ABSENT"}]


def test_missing_evidence_is_positive_uncovered_count():
    assert recompute(rows(), EXPECTED) == 2


@pytest.mark.parametrize("damage", ["empty", "partial", "duplicate", "stale", "altered", "failed", "false_coverage", "empty_rules"])
def test_invalid_populations_or_claims_refuse_measurement(damage):
    data = deepcopy(rows())
    if damage == "empty":
        data = []
    elif damage == "partial":
        data = data[:1]
    elif damage == "duplicate":
        data[1] = data[0]
    elif damage == "stale":
        data[0]["contract_version"] = 999
    elif damage == "altered":
        data[0]["covered_rules"] = ["unrelated"]
    elif damage == "failed":
        data[0]["evidence_status"] = "REPLAY_FAILED"
    elif damage == "false_coverage":
        data[1]["covered_rules"] = ["objective"]
    else:
        data[0]["declared_rules"] = []
    with pytest.raises(ValueError):
        recompute(data, EXPECTED)
