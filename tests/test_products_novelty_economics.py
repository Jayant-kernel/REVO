"""Novelty and run-economics tests (production-002 preparation)."""

from tests.product_fixtures import build_product_fixture
from verified_data_factory.products import (
    collect_run_economics,
    compute_novelty,
    economics_summary,
    structural_signature,
)


def _golden_dicts():
    goldens, _quality_by_id, _ = build_product_fixture()
    return [g.model_dump(mode="json", by_alias=True) for g in goldens]


def test_novelty_identical_pool_has_no_novelty():
    pool = _golden_dicts()
    report = compute_novelty(new_golden=pool, pool_golden=pool)
    assert report.new_total == report.pool_total == len(pool)
    assert report.novel_golden == 0
    assert report.exact_duplicates == len(pool)
    assert report.novel_tasks == 0 and report.novel_schemas == 0


def test_novelty_detects_new_records():
    pool = _golden_dicts()
    extra = dict(pool[0])
    extra["candidate_id"] = "cand-new"
    extra["candidate_solution"] = "SELECT count(*) AS n FROM orders WHERE amount > 99999;"
    extra["task"] = {**extra["task"], "task_id": "task-new"}
    report = compute_novelty(new_golden=[extra], pool_golden=pool)
    assert report.novel_golden == 1
    assert report.novel_ids == ["cand-new"]
    assert report.novel_tasks == 1
    assert report.novel_sql_structures >= 1


def test_novelty_semantic_group_overlap():
    pool = _golden_dicts()
    extra = dict(pool[0])
    extra["candidate_id"] = "cand-sem"
    extra["candidate_solution"] = "SELECT 1;"
    extra["quality"] = {"semantic_duplicate_group": "sem-a"}
    report = compute_novelty(new_golden=[extra], pool_golden=pool, pool_semantic_groups={"sem-a"})
    assert report.semantic_duplicates == 1
    assert report.novel_golden == 0


def test_structural_signature_stable():
    sql = "select  a\n from t  where x=1"
    assert structural_signature(sql) == structural_signature("SELECT a FROM t WHERE x = 1")
    assert structural_signature("SELECT a FROM t") != structural_signature(
        "SELECT a, b FROM t JOIN u ON t.id = u.id GROUP BY a"
    )


def test_economics_observed_and_unknown():
    econ = collect_run_economics(
        generation_wall_s=600.0,
        generation_candidates=300,
        prompt_tokens=1000.0,
        completion_tokens=500.0,
        model_calls=300,
        executions=300,
        verifications=300,
        passes=100,
        goldens=49,
        novel_goldens=20,
        artifact_bytes=1024.0,
    )
    assert econ.per_candidate_s.value == 2.0
    assert econ.per_golden_s.value == 600.0 / 49
    assert econ.per_novel_golden_s.value == 30.0
    assert econ.per_candidate_s.basis == "OBSERVED"
    assert econ.power_watts.basis == "UNKNOWN"
    assert econ.power_watts.value is None
    assert econ.projected_s_for_1000_golden.basis == "PROJECTED"
    assert econ.projected_s_for_10000_golden.value == econ.per_golden_s.value * 10000
    assert econ.monetary == {}
    summary = economics_summary(econ)
    assert summary["per_golden_s"]["value"] == econ.per_golden_s.value


def test_economics_money_only_with_price_table():
    econ = collect_run_economics(price_table={"usd_per_second": 0.01})
    assert econ.monetary["usd_per_second"].basis == "ASSUMED"
    assert econ.per_golden_s.basis == "UNKNOWN"
    assert econ.projected_s_for_1000_golden.value is None
