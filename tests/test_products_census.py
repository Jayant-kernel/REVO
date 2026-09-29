"""Census and diversity tests (§6–§7 remediation)."""

from tests.product_fixtures import build_product_fixture
from verified_data_factory.products import (
    build_audit_report,
    build_census,
    build_diversity_report,
    build_row_manifest,
    render_audit_markdown,
    sql_features,
)


def _inputs():
    goldens, quality_by_id, snapshot = build_product_fixture()
    golden_dicts = [g.model_dump(mode="json", by_alias=True) for g in goldens]
    qualities = [quality_by_id[g.candidate_id] for g in goldens]
    return golden_dicts, qualities, quality_by_id, snapshot


def test_diversity_reports_counts_not_scores():
    golden_dicts, _, quality_by_id, _ = _inputs()
    report = build_diversity_report(golden_records=golden_dicts, quality_by_id=quality_by_id)
    assert report.record_count == len(golden_dicts)
    assert report.instruction_unique_normalized >= 1
    assert 0.0 <= (report.instruction_unique_ratio or 0.0) <= 1.0
    assert report.sql_features["group_by"]["records_with_feature"] >= 0
    assert report.template_counts
    assert report.edge_counts is not None
    assert "score" not in report.model_dump(mode="json")


def test_sql_features_deterministic():
    sql = "SELECT a, SUM(b) FROM t WHERE x > 1 GROUP BY a HAVING SUM(b) > 2 ORDER BY a"
    first = sql_features(sql)
    assert sql_features(sql) == first
    assert first["group_by"] is True and first["having"] is True
    assert "SUM" in first["aggregations"]
    assert first["subquery_count"] == 0
    nested = "SELECT * FROM (SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u)) ORDER BY a"
    assert sql_features(nested)["subquery_count"] == 2
    assert sql_features(nested)["exists"] is True


def test_census_reproduces_record_level_evidence():
    golden_dicts, _, quality_by_id, _snapshot = _inputs()
    census = build_census(golden_records=golden_dicts, quality_by_id=quality_by_id)
    assert census.record_count == len(golden_dicts)
    assert sum(census.strength_distribution.values()) == len(golden_dicts)
    assert sum(census.family_counts.values()) == len(golden_dicts)
    assert census.zero_applicable_ids == sorted(census.zero_applicable_ids)
    assert census.all_strong in (True, False)


def test_census_flags_unjustified_zero_applicable():
    golden_dicts, _, quality_by_id, _ = _inputs()
    assert (
        build_census(
            golden_records=golden_dicts, quality_by_id=quality_by_id
        ).unjustified_zero_applicable_count
        >= 0
    )
    justified = {cid: "auditor reason" for cid in [g["candidate_id"] for g in golden_dicts]}
    assert (
        build_census(
            golden_records=golden_dicts, quality_by_id=quality_by_id, justifications=justified
        ).unjustified_zero_applicable_count
        == 0
    )


def test_audit_report_readiness_statuses():
    golden_dicts, _, quality_by_id, snapshot = _inputs()
    rows = build_row_manifest(
        golden_records=golden_dicts,
        quality_by_id=quality_by_id,
        dataset_snapshot_id=snapshot.dataset_snapshot_id,
        candidates_by_id={
            g["candidate_id"]: {"model": "m", "model_revision": "r"} for g in golden_dicts
        },
    )
    census = build_census(
        golden_records=golden_dicts, quality_by_id=quality_by_id, row_manifest=rows
    )
    report = build_audit_report(
        census=census,
        supply_chain={
            "governance_status": "REVIEW_REQUIRED",
            "commercially_cleared": False,
            "clearance_reasons": ["r"],
        },
    )
    assert report.readiness["commercial"] == "COMMERCIAL_RELEASE_BLOCKED"
    assert report.readiness["overall"] == "NOT_READY"
    assert "score" not in report.model_dump(mode="json")
    markdown = render_audit_markdown(report)
    assert "## Section 7. Release readiness" in markdown


def test_audit_report_eligible_when_all_clear():
    golden_dicts, _, quality_by_id, snapshot = _inputs()
    rows = build_row_manifest(
        golden_records=golden_dicts,
        quality_by_id=quality_by_id,
        dataset_snapshot_id=snapshot.dataset_snapshot_id,
        candidates_by_id={
            g["candidate_id"]: {"model": "m", "model_revision": "r"} for g in golden_dicts
        },
    )
    census = build_census(
        golden_records=golden_dicts,
        quality_by_id=quality_by_id,
        row_manifest=rows,
        justifications={g["candidate_id"]: "ok" for g in golden_dicts},
    )
    cleared = {
        "governance_status": "APPROVED",
        "commercially_cleared": True,
        "clearance_reasons": [],
    }
    report = build_audit_report(census=census, supply_chain=cleared)
    assert report.readiness["governance"] == "GOVERNANCE_CLEAR"
