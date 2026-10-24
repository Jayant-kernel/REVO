"""Regression evidence from retained model outputs, never regenerated SQL."""
import json
from collections import Counter

import duckdb
import pytest

from tests.test_pareto_shipping_profile import ROOT, TASK, execute, matches
from verified_data_factory.verification.qualification import pareto_shipping_profile as p
from verified_data_factory.verification.qualification.pareto_shipping_candidate_transforms import (
    candidate_proofs,
    structural_checks,
)

RUN = ROOT / "runs/company-pareto-shipping-cpu-v30-001"
RECORDED = [
    json.loads((RUN / f"attempt-{index:03}/generation.json").read_text())["candidate_solution"]
    for index in range(2)
]


def independent_rows(tables):
    """SQL-free pairwise definition, independent of the profile oracle."""
    rows = tables["options"]
    survivors = []
    for a in rows:
        metrics = (a["cost_cents"], a["duration_minutes"])
        if None in metrics:
            continue
        dominated = False
        for b in rows:
            other = (b["cost_cents"], b["duration_minutes"])
            if b["lane"] != a["lane"] or None in other:
                continue
            if all(x <= y for x, y in zip(other, metrics, strict=True)) and other != metrics:
                dominated = True
        if not dominated:
            survivors.append([a[field] for field in p.FIELDS])
    return sorted(survivors)


@pytest.mark.parametrize("candidate", RECORDED, ids=["attempt-000", "attempt-001"])
def test_recorded_sql_900_frames_independent_oracle(candidate):
    counts = Counter()
    for seed in (1, 43, 94001):
        for index in range(300):
            tables = p.fixture(seed, index)
            columns, types, rows = execute(candidate["candidate_sql"], tables)
            assert columns == list(p.FIELDS)
            assert types == ["INTEGER", "VARCHAR", "INTEGER", "INTEGER"]
            assert rows == independent_rows(tables), (seed, index)
            counts.update(p.observed(tables)[2])
    assert counts["empty_input"] == 69
    assert all(counts[name] >= 60 for name in p.BEHAVIORS)


@pytest.mark.parametrize("candidate", RECORDED, ids=["attempt-000", "attempt-001"])
@pytest.mark.parametrize("rename", [False, True])
def test_actual_candidate_mutations_and_self_attribution(candidate, rename):
    sql = candidate["candidate_sql"]
    if rename:
        sql = sql.replace("o2", "competitor").replace("options o\n", "options proposal\n").replace(
            "o.", "proposal.")
        sql = sql.replace("competitor.cost_cents <= proposal.cost_cents", "SWAP_TERM")
        sql = sql.replace("competitor.duration_minutes <= proposal.duration_minutes",
                          "competitor.cost_cents <= proposal.cost_cents")
        sql = sql.replace("SWAP_TERM", "competitor.duration_minutes <= proposal.duration_minutes")
    assert structural_checks(TASK, sql)["status"] == "PASS"
    proofs = candidate_proofs(sql, p.REFERENCE, p.proofs(p.REFERENCE))
    assert proofs is not None
    for key, spec in proofs.items():
        if "wrong_sql" in spec:
            assert execute(sql, spec["witness"])[2] == independent_rows(spec["witness"])
            assert not matches(spec["wrong_sql"], spec["witness"]), key
            if rename:
                assert "proposal" in spec["wrong_sql"] and "competitor" in spec["wrong_sql"]
        elif key in p.STRUCTURAL_KEYS:
            assert matches(spec["structural_sql"], spec["witness"])
            assert structural_checks(TASK, spec["structural_sql"])["status"] == "FAIL"
    singleton = {"options": [p.option()]}
    assert execute(proofs["self"]["wrong_sql"], singleton)[2] == []
    assert independent_rows(singleton) == [[1, "A", 10, 20]]
    incomplete = {"options": [p.option(), p.option(2, cost=None, duration=0)]}
    assert matches(sql, incomplete)
    assert not matches(proofs["incomplete"]["wrong_sql"], incomplete)


def test_sql_three_valued_comparisons_exclude_incomplete_competitors():
    con = duckdb.connect(config={"enable_external_access": "false"})
    try:
        assert con.execute("SELECT (NULL <= 10) AND (0 <= 20) AND "
                           "((NULL < 10) OR (0 < 20))").fetchone() == (None,)
        assert con.execute("SELECT 1 WHERE (NULL <= 10) AND (0 <= 20) AND "
                           "((NULL < 10) OR (0 < 20))").fetchall() == []
    finally:
        con.close()


@pytest.mark.parametrize("candidate", RECORDED)
def test_scope_and_unsupported_trees_fail_closed(candidate):
    sql = candidate["candidate_sql"]
    variants = [sql + " LIMIT 1", sql.replace("o2.lane = o.lane", "o2.lane = lane"),
                sql.replace("o2.cost_cents <= o.cost_cents", "o2.cost_cents <= cost_cents"),
                sql.replace("o2.option_id != o.option_id", "o2.option_id = o.option_id"),
                sql.replace("(o2.cost_cents < o.cost_cents OR o2.duration_minutes < o.duration_minutes)",
                            "TRUE").replace("o2.option_id != o.option_id", "TRUE"),
                sql.replace(" OR ", " AND "),
                sql.replace("o2.cost_cents <= o.cost_cents", "o2.cost_cents >= o.cost_cents"),
                sql.replace("o2.cost_cents <= o.cost_cents", "o2.cost_cents <= 2147483646"),
                sql.replace("o2.cost_cents <= o.cost_cents", "o2.cost_cents <= (SELECT MIN(cost_cents) FROM options)"),
                sql.replace("o2.duration_minutes <= o.duration_minutes", "o2.duration_minutes <= (SELECT MAX(duration_minutes) FROM options)"),
                sql.replace("o2.cost_cents <= o.cost_cents", "(o2.cost_cents <= o.cost_cents OR TRUE)")]
    for wrong in variants:
        assert candidate_proofs(wrong, p.REFERENCE, p.proofs(p.REFERENCE)) is None
        assert structural_checks(TASK, wrong)["status"] in {"INCONCLUSIVE", "FAIL"}
    assert structural_checks(TASK, sql + " LIMIT 1")["status"] == "INCONCLUSIVE"
    for control in p.structural_controls().values():
        assert structural_checks(TASK, control)["status"] == "FAIL"


def test_antijoin_decorative_not_exists_is_not_structural_evidence():
    sql = ("SELECT o.option_id,o.lane,o.cost_cents,o.duration_minutes FROM options o "
           "LEFT JOIN options p ON p.lane=o.lane AND p.cost_cents<=o.cost_cents "
           "AND p.duration_minutes<=o.duration_minutes "
           "AND (p.cost_cents<o.cost_cents OR p.duration_minutes<o.duration_minutes) "
           "WHERE o.cost_cents IS NOT NULL AND o.duration_minutes IS NOT NULL "
           "AND p.option_id IS NULL AND NOT EXISTS (SELECT 1 FROM options z WHERE FALSE) "
           "ORDER BY o.option_id")
    assert matches(sql, p.rich_fixture())
    assert structural_checks(TASK, sql)["status"] == "FAIL"
    assert candidate_proofs(sql, p.REFERENCE, p.proofs(p.REFERENCE)) is None


def test_valid_having_correlation_abstains_instead_of_false_failure():
    sql = p.REFERENCE.replace("WHERE p.lane = o.lane", "GROUP BY p.lane,p.cost_cents,p.duration_minutes HAVING p.lane = o.lane")
    for tables in ({"options": []}, {"options": [p.option()]}, p.rich_fixture()):
        assert matches(sql, tables)
    assert candidate_proofs(sql, p.REFERENCE, p.proofs(p.REFERENCE)) is None
    assert structural_checks(TASK, sql)["status"] == "INCONCLUSIVE"
