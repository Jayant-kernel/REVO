"""Export + reproducibility + config tests for Phase 5."""

import json

from tests.quality_dataset import build_fixture_dataset
from verified_data_factory.quality import (
    QualityConfig,
    analyze_dataset,
    export_dataset,
    load_quality_config,
)
from verified_data_factory.quality.errors import QualityConfigError


def test_export_layout_and_stable_ordering(tmp_path):
    analysis = analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=0.2))
    records = {r.candidate.candidate_id: r for r in analysis.records}
    paths = export_dataset(
        analysis.qualities,
        records,
        analysis.health.model_dump(mode="json"),
        [i.model_dump(mode="json") for i in analysis.audit_sample.items],
        tmp_path,
    )
    assert set(paths) == {"golden", "excluded", "inconclusive", "audit_required", "health", "audit"}
    golden_ids = [
        json.loads(line)["candidate_id"]
        for line in (tmp_path / "golden.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert golden_ids == sorted(golden_ids)
    assert len(golden_ids) == sum(1 for q in analysis.qualities if q.decision == "GOLDEN")
    record = json.loads((tmp_path / "golden.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert set(record) >= {
        "record_id",
        "record_schema_version",
        "task",
        "instruction",
        "schema",
        "fixture",
        "candidate_solution",
        "verification",
        "quality",
    }
    assert record["record_id"].startswith("sha256:")


def test_export_round_trip(tmp_path):
    analysis = analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=0.0))
    records = {r.candidate.candidate_id: r for r in analysis.records}
    export_dataset(
        analysis.qualities,
        records,
        analysis.health.model_dump(mode="json"),
        [i.model_dump(mode="json") for i in analysis.audit_sample.items],
        tmp_path,
    )
    health = json.loads((tmp_path / "dataset_health.json").read_text(encoding="utf-8"))
    assert health["production"]["golden_count"] == sum(
        1 for q in analysis.qualities if q.decision == "GOLDEN"
    )
    audit_lines = (tmp_path / "audit_sample.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(audit_lines) == analysis.audit_sample.sampled_count


def test_record_id_binds_task_and_sql_content():
    from verified_data_factory.quality.export import golden_record_for

    analysis = analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=0.0))
    quality = next(q for q in analysis.qualities if q.decision == "GOLDEN")
    source = next(r for r in analysis.records if r.candidate.candidate_id == quality.candidate_id)
    first = golden_record_for(quality, source)
    changed_candidate = source.candidate.model_copy(
        update={"candidate_sql": (source.candidate.candidate_sql or "") + "\n-- changed"}
    )
    second = golden_record_for(quality, source.model_copy(update={"candidate": changed_candidate}))
    assert first.record_id != second.record_id
    assert first.record_id == golden_record_for(quality, source).record_id


def test_health_contamination_schema_preserves_counts_and_types():
    analysis = analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=0.0))
    contamination = analysis.health.model_dump(mode="json")["contamination"]
    assert set(contamination) == {
        "flagged_count",
        "contaminated_rate",
        "split_overlap_count",
        "flags_by_type",
    }
    assert isinstance(contamination["flagged_count"], int)
    assert isinstance(contamination["flags_by_type"], dict)


def test_full_pipeline_twice_identical(tmp_path):
    first = analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=0.25))
    second = analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=0.25))

    def snapshot(analysis):
        return {
            "decisions": [
                (q.candidate_id, q.decision, tuple(q.decision_reasons)) for q in analysis.qualities
            ],
            "groups": [
                (g.group_id, g.duplicate_type, tuple(g.member_ids), g.representative_id)
                for g in analysis.duplicates.groups
            ],
            "health": analysis.health.model_dump(mode="json"),
            "audit": [i.model_dump(mode="json") for i in analysis.audit_sample.items],
        }

    assert snapshot(first) == snapshot(second)


def test_export_bytes_identical(tmp_path):
    import shutil

    first_dir, second_dir = tmp_path / "a", tmp_path / "b"
    for directory in (first_dir, second_dir):
        analysis = analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=0.25))
        records = {r.candidate.candidate_id: r for r in analysis.records}
        export_dataset(
            analysis.qualities,
            records,
            analysis.health.model_dump(mode="json"),
            [i.model_dump(mode="json") for i in analysis.audit_sample.items],
            directory,
        )
    for name in (
        "golden.jsonl",
        "excluded.jsonl",
        "inconclusive.jsonl",
        "audit_required.jsonl",
        "dataset_health.json",
        "audit_sample.jsonl",
    ):
        assert (first_dir / name).read_bytes() == (second_dir / name).read_bytes(), name
    shutil.rmtree(first_dir, ignore_errors=True)


def test_invariants_monotonicity_and_safety():
    records = build_fixture_dataset()
    base = analyze_dataset(records, QualityConfig(audit_rate=0.0))
    base_unique = len({q.candidate_id for q in base.qualities})
    doubled = analyze_dataset(records + records, QualityConfig(audit_rate=0.0))
    assert len({q.candidate_id for q in doubled.qualities}) == base_unique
    for quality in doubled.qualities:
        if quality.verification.verdict == "FAIL":
            assert quality.decision == "EXCLUDED"
        if quality.verification.verdict == "INCONCLUSIVE" and quality.task_quality.valid:
            assert quality.decision == "INCONCLUSIVE"
        if any(f.hard for f in quality.contamination_flags):
            assert quality.decision == "EXCLUDED"


def test_config_defaults_yaml_and_invalid(tmp_path):
    import pytest

    config = QualityConfig()
    assert config.mutation_min_score == 0.9
    assert config.audit_rate == 0.2
    assert config.config_version == "1.1-scoped-overlap"
    path = tmp_path / "q.yaml"
    path.write_text("quality:\n  mutation_min_score: 0.5\n  audit_rate: 0.1\n", encoding="utf-8")
    loaded = load_quality_config(path)
    assert loaded.mutation_min_score == 0.5
    bad = tmp_path / "bad.yaml"
    bad.write_text("quality:\n  audit_rate: 99\n", encoding="utf-8")
    with pytest.raises(QualityConfigError):
        load_quality_config(bad)
