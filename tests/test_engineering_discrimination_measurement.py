from copy import deepcopy

import pytest

from scripts.engineering_discrimination_measurement import CATEGORIES, METRICS, recompute

POPULATION = [{"contract_id": "a", "contract_version": 1}]
THRESHOLDS = {"minimum_wrong_challenges_per_contract": 20, "minimum_correct_alternatives_per_contract": 3,
              "minimum_distinct_fixtures_including_original": 4, "minimum_discriminating_relations_per_contract": 2}


def test_absent_categories_never_create_zero_deficiencies():
    rows = [{**POPULATION[0], "categories": {category: {"status": "ABSENT"} for category in CATEGORIES}}]
    assert recompute(rows, POPULATION, THRESHOLDS) == dict.fromkeys(METRICS.values(), 1)


@pytest.mark.parametrize("damage", ["empty", "duplicate", "wrong_version", "missing_category", "failed"])
def test_incomplete_or_failed_measurement_refused(damage):
    rows = [{**POPULATION[0], "categories": {category: {"status": "ABSENT"} for category in CATEGORIES}}]
    rows = deepcopy(rows)
    if damage == "empty":
        rows = []
    elif damage == "duplicate":
        rows.append(rows[0])
    elif damage == "wrong_version":
        rows[0]["contract_version"] = 999
    elif damage == "missing_category":
        del rows[0]["categories"]["relations"]
    else:
        rows[0]["categories"]["challenge"]["status"] = "FAILED"
    with pytest.raises(ValueError):
        recompute(rows, POPULATION, THRESHOLDS)
