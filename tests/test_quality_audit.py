"""Contamination and audit tests."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from tests.quality_dataset import build_fixture_dataset
from verified_data_factory.quality import QualityConfig, analyze_dataset, record_audit_result
from verified_data_factory.quality.contamination import analyze_contamination
from verified_data_factory.task_engine import canonical_task_dict


def _analysis(**overrides):
    config = QualityConfig(audit_rate=0.3, **overrides)
    return analyze_dataset(build_fixture_dataset(), config)


def test_exact_overlap_private_eval_flagged_hard():
    analysis = _analysis()
    by_id = {q.candidate_id: q for q in analysis.qualities}
    flagged = [
        q
        for q in by_id.values()
        if any(f.flag_type == "EXACT_OVERLAP_PRIVATE_EVAL" for f in q.contamination_flags)
    ]
    assert len(flagged) == 1
    assert flagged[0].role == "TRAIN"
    assert any(f.hard for f in flagged[0].contamination_flags)
    assert flagged[0].decision == "EXCLUDED"
    assert "CONTAMINATION" in flagged[0].decision_reasons


def test_exact_task_overlap_distinguishes_siblings_from_other_tasks():
    qualities = [
        SimpleNamespace(candidate_id="a", task_id="task-1", role="TRAIN", template_id="t", template_version=1),
        SimpleNamespace(candidate_id="b", task_id="task-1", role="TRAIN", template_id="t", template_version=1),
        SimpleNamespace(candidate_id="c", task_id="task-2", role="TRAIN", template_id="t", template_version=1),
    ]
    flags, _ = analyze_contamination(
        qualities,
        {"a": "same canonical task", "b": "same canonical task", "c": "same canonical task"},
        {"a": "SELECT 1", "b": "SELECT 2", "c": "SELECT 3"},
        QualityConfig(),
    )
    assert any(f.scope == "SAME_TASK_SIBLINGS" for f in flags["a"])
    assert any(f.scope == "CROSS_TASK" for f in flags["a"])
    assert not any(f.scope == "SAME_TASK_SIBLINGS" for f in flags["c"])


def test_template_leakage_and_normalized_overlap_flagged_soft():
    analysis = _analysis()
    assert analysis.contamination.flags_by_type.get("TEMPLATE_LEAKAGE", 0) >= 2
    assert analysis.contamination.flags_by_type.get("NORMALIZED_OVERLAP", 0) >= 2
    assert analysis.contamination.split_overlap_count >= 2


def test_known_source_registry_hit_blocks():
    records = build_fixture_dataset()
    target = records[0]
    digest = hashlib.sha256(
        json.dumps(canonical_task_dict(target.task), sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    analysis = analyze_dataset(records, QualityConfig(audit_rate=0.0, known_source_hashes=[digest]))
    by_id = {q.candidate_id: q for q in analysis.qualities}
    assert any(
        f.flag_type == "KNOWN_SOURCE" and f.hard
        for f in by_id[target.candidate.candidate_id].contamination_flags
    )
    assert by_id[target.candidate.candidate_id].decision == "EXCLUDED"


def test_clean_record_has_no_hard_flags():
    analysis = _analysis()
    by_id = {q.candidate_id: q for q in analysis.qualities}
    clean = [q for q in by_id.values() if q.family == "aggregation"]
    assert clean
    for quality in clean:
        assert not any(f.hard for f in quality.contamination_flags), quality.contamination_flags


def test_audit_sampling_deterministic_and_risk_ordered():
    first = _analysis()
    second = _analysis()
    assert [i.audit_id for i in first.audit_sample.items] == [
        i.audit_id for i in second.audit_sample.items
    ]
    assert first.audit_sample.sampled_count > 0
    assert any(i.risk_band in ("HIGH", "MEDIUM") for i in first.audit_sample.items)
    by_risk = sorted(first.audit_sample.items, key=lambda i: -i.risk_score)
    assert first.audit_sample.items != [] and by_risk[0].risk_score >= by_risk[-1].risk_score


def test_high_risk_records_selected():
    analysis = analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=1.0))
    sampled = {i.candidate_id for i in analysis.audit_sample.items}
    assert analysis.audit_sample.sampled_count == len(analysis.qualities)
    by_id = {q.candidate_id: q for q in analysis.qualities}
    weak = [q.candidate_id for q in by_id.values() if "MUTATION_THRESHOLD" in q.decision_reasons]
    assert weak and all(c in sampled for c in weak)


def test_low_risk_records_can_be_sampled():
    analysis = analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=1.0))
    assert analysis.audit_sample.sampled_count == len(analysis.qualities)
    assert any(i.risk_band == "LOW" for i in analysis.audit_sample.items)


def test_audit_result_recording_and_unknown_id():
    analysis = _analysis()
    item = analysis.audit_sample.items[0]
    updated = record_audit_result(
        analysis.audit_sample, item.candidate_id, "PASS", note="looks good"
    )
    assert next(i for i in updated.items if i.candidate_id == item.candidate_id).result == "PASS"
    with pytest.raises(ValueError):
        record_audit_result(analysis.audit_sample, "no-such-candidate", "PASS")
    with pytest.raises(ValueError):
        record_audit_result(analysis.audit_sample, item.candidate_id, "PENDING")
