"""Duplicate detection tests at all three levels."""

from tests.quality_dataset import build_fixture_dataset
from verified_data_factory.quality import (
    QualityConfig,
    analyze_dataset,
    normalize_sql,
    sql_fingerprint,
)


def _analysis():
    return analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=0.0))


def test_normalize_folds_case_glue_literals_and_numbers():
    assert normalize_sql("select  a   FROM t;") == normalize_sql("SELECT a FROM t")
    assert normalize_sql("SELECT sum(x) FROM t;") == normalize_sql("SELECT SUM(x) FROM t")
    assert normalize_sql("SELECT * FROM t WHERE a = 'Xyz' AND b = 42;") == normalize_sql(
        "SELECT * FROM t WHERE a = 'Abc' AND b = 7;"
    )
    assert normalize_sql("SELECT 1; -- comment") == normalize_sql("SELECT 1")
    assert sql_fingerprint("select 1;") == sql_fingerprint("SELECT 1")


def test_exact_duplicates_grouped():
    analysis = _analysis()
    exact = [g for g in analysis.duplicates.groups if g.duplicate_type == "EXACT"]
    assert len(exact) == 2
    pair = next(g for g in exact if len(g.member_ids) == 2)
    assert pair.representative_id == min(pair.member_ids)


def test_formatting_only_is_structural_not_exact():
    analysis = _analysis()
    structural = [g for g in analysis.duplicates.groups if g.duplicate_type == "STRUCTURAL"]
    assert any(len(g.member_ids) >= 3 for g in structural)
    exact_ids = {
        i for g in analysis.duplicates.groups if g.duplicate_type == "EXACT" for i in g.member_ids
    }
    structural_ids = {i for g in structural for i in g.member_ids}
    assert structural_ids - exact_ids, "formatting-only pair must exist outside exact groups"


def test_semantic_duplicates_grouped():
    analysis = _analysis()
    semantic = [g for g in analysis.duplicates.groups if g.duplicate_type == "SEMANTIC"]
    assert any(len(g.member_ids) >= 3 for g in semantic)


def test_unrelated_records_distinct():
    analysis = _analysis()
    grouped = {i for g in analysis.duplicates.groups for i in g.member_ids}
    lone = next(
        q.candidate_id
        for q in analysis.qualities
        if q.family == "aggregation" and q.candidate_id not in grouped
    )
    assert lone


def test_group_ids_stable_and_representative_deterministic():
    first = analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=0.0))
    second = analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=0.0))
    assert [g.group_id for g in first.duplicates.groups] == [
        g.group_id for g in second.duplicates.groups
    ]
    assert [g.representative_id for g in first.duplicates.groups] == [
        g.representative_id for g in second.duplicates.groups
    ]


def test_duplicate_fields_populated_on_records():
    analysis = _analysis()
    by_id = {q.candidate_id: q for q in analysis.qualities}
    grouped = [q for q in by_id.values() if q.exact_duplicate_group or q.semantic_duplicate_group]
    assert grouped
    for quality in grouped:
        members = [g for g in analysis.duplicates.groups if quality.candidate_id in g.member_ids]
        assert members
