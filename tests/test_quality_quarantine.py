"""Quarantine mechanism tests (§2 remediation)."""

import pytest

from tests.quality_dataset import build_fixture_dataset
from verified_data_factory.quality import (
    QualityConfig,
    QuarantineEntry,
    analyze_dataset,
    load_quarantine,
    quarantine_map,
    quarantined_ids,
    select_golden,
    write_quarantine_artifact,
)
from verified_data_factory.quality.errors import QualityConfigError


def _entry(candidate_id, eligible=False):
    return QuarantineEntry(
        candidate_id=candidate_id,
        reason="UNKNOWN strength with zero applicable mutants; no justification on file",
        applicable_mutants=0,
        mutation_score=None,
        original_decision="GOLDEN",
        release_eligible=eligible,
    )


def test_quarantined_golden_demoted_before_dedup():
    records = build_fixture_dataset()
    analysis = analyze_dataset(records, QualityConfig(audit_rate=0.0))
    golden_ids = [q.candidate_id for q in analysis.qualities if q.decision == "GOLDEN"]
    assert golden_ids
    target = min(golden_ids)
    reselected = select_golden(
        analysis.qualities, QualityConfig(audit_rate=0.0), {}, quarantined={target: "audit hold"}
    )
    by_id = {q.candidate_id: q for q in reselected}
    assert by_id[target].decision == "EXCLUDED"
    assert "QUARANTINED" in by_id[target].decision_reasons
    # Non-quarantined goldens keep their decisions.
    for q in reselected:
        if q.candidate_id != target and q.candidate_id in golden_ids:
            assert q.decision == "GOLDEN"


def test_quarantine_roundtrip_and_ids(tmp_path):
    entry = _entry("cand-001")
    path = write_quarantine_artifact(entry, tmp_path / "q" / "entry.json")
    import json

    (tmp_path / "qlist.json").write_text(json.dumps([entry.model_dump(mode="json")]))
    loaded = load_quarantine(tmp_path / "qlist.json")
    assert loaded[0].candidate_id == "cand-001"
    assert quarantined_ids(loaded) == {"cand-001"}
    assert quarantined_ids([_entry("cand-002", eligible=True)]) == set()
    assert path.exists()


def test_quarantine_map_deterministic():
    entries = [_entry("b"), _entry("a")]
    mapped = quarantine_map(entries)
    assert list(mapped) == ["a", "b"]


def test_malformed_quarantine_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"not": "a list"}', encoding="utf-8")
    with pytest.raises(QualityConfigError):
        load_quarantine(bad)
    bad2 = tmp_path / "bad2.json"
    bad2.write_text('[{"candidate_id": ""}]', encoding="utf-8")
    with pytest.raises(QualityConfigError):
        load_quarantine(bad2)


def test_analyze_dataset_accepts_quarantine():
    records = build_fixture_dataset()
    base = analyze_dataset(records, QualityConfig(audit_rate=0.0))
    target = min(q.candidate_id for q in base.qualities if q.decision == "GOLDEN")
    rerun = analyze_dataset(records, QualityConfig(audit_rate=0.0), quarantined={target: "hold"})
    by_id = {q.candidate_id: q for q in rerun.qualities}
    assert by_id[target].decision == "EXCLUDED"
    assert "QUARANTINED" in by_id[target].decision_reasons
