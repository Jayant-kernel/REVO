"""Per-row manifest tests (§5 remediation)."""

from tests.product_fixtures import build_product_fixture
from verified_data_factory.products import (
    build_row_manifest,
    manifest_identity_summary,
    public_row_view,
    read_row_manifest,
    validate_row_manifest,
    write_row_manifest,
)


def _inputs():
    goldens, quality_by_id, snapshot = build_product_fixture()
    golden_dicts = [g.model_dump(mode="json", by_alias=True) for g in goldens]
    candidates_by_id = {
        g.candidate_id: {
            "model": "test-model",
            "model_revision": "test-rev",
            "prompt_version": "sql-v1",
        }
        for g in goldens
    }
    return golden_dicts, quality_by_id, snapshot, candidates_by_id


def test_build_validate_roundtrip(tmp_path):
    golden_dicts, quality_by_id, snapshot, candidates_by_id = _inputs()
    rows = build_row_manifest(
        golden_records=golden_dicts,
        quality_by_id=quality_by_id,
        dataset_snapshot_id=snapshot.dataset_snapshot_id,
        candidates_by_id=candidates_by_id,
        release_id="sha256:rel",
        generation_run_id="run-1",
    )
    assert len(rows) == len(golden_dicts)
    assert validate_row_manifest(rows, require_snapshot=snapshot.dataset_snapshot_id) == []
    path = write_row_manifest(rows, tmp_path / "row-manifest.jsonl")
    assert [r.record_id for r in read_row_manifest(path)] == sorted(r.record_id for r in rows)


def test_public_view_drops_internal_ids():
    golden_dicts, quality_by_id, snapshot, candidates_by_id = _inputs()
    rows = build_row_manifest(
        golden_records=golden_dicts[:2],
        quality_by_id=quality_by_id,
        dataset_snapshot_id=snapshot.dataset_snapshot_id,
        candidates_by_id=candidates_by_id,
        generation_run_id="run-1",
    )
    view = public_row_view(rows[0])
    assert "generation_run_id" not in view
    assert "execution_run_id" not in view
    assert view["candidate_id"] == rows[0].candidate_id


def test_missing_provenance_fails():
    golden_dicts, quality_by_id, snapshot, candidates_by_id = _inputs()
    rows = build_row_manifest(
        golden_records=golden_dicts[:2],
        quality_by_id=quality_by_id,
        dataset_snapshot_id=snapshot.dataset_snapshot_id,
        candidates_by_id=candidates_by_id,
    )
    broken = rows[0].model_copy(update={"model_name": "unknown"})
    violations = validate_row_manifest([broken, rows[1]])
    assert any("missing required provenance" in v for v in violations)


def test_mixed_run_identities_flagged():
    golden_dicts, quality_by_id, snapshot, candidates_by_id = _inputs()
    rows = build_row_manifest(
        golden_records=golden_dicts[:4],
        quality_by_id=quality_by_id,
        dataset_snapshot_id=snapshot.dataset_snapshot_id,
        candidates_by_id=candidates_by_id,
    )
    mixed = [rows[0].model_copy(update={"model_name": "other-model"})] + rows[1:]
    violations = validate_row_manifest(mixed)
    assert any("mixes run identities" in v for v in violations)


def test_quarantined_rows_rejected_and_snapshot_pinned():
    golden_dicts, quality_by_id, snapshot, candidates_by_id = _inputs()
    rows = build_row_manifest(
        golden_records=golden_dicts[:3],
        quality_by_id=quality_by_id,
        dataset_snapshot_id=snapshot.dataset_snapshot_id,
        candidates_by_id=candidates_by_id,
    )
    violations = validate_row_manifest(
        rows,
        require_snapshot="sha256:other",
        quarantined_ids={rows[0].record_id},
    )
    assert any("quarantined record present" in v for v in violations)
    assert any("!= required" in v for v in violations)


def test_identity_summary_distinguishes_runs():
    golden_dicts, quality_by_id, snapshot, candidates_by_id = _inputs()
    rows = build_row_manifest(
        golden_records=golden_dicts[:3],
        quality_by_id=quality_by_id,
        dataset_snapshot_id=snapshot.dataset_snapshot_id,
        candidates_by_id=candidates_by_id,
    )
    summary = manifest_identity_summary(rows)
    assert summary["record_count"] == 3
    assert len(summary["models"]) == 1
