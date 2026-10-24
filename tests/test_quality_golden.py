"""Golden selection tests: PASS is necessary, never sufficient."""

from tests.quality_dataset import build_fixture_dataset
from verified_data_factory.quality import QualityConfig, analyze_dataset


def _analysis(**overrides):
    config = QualityConfig(audit_rate=0.0, **overrides)
    return analyze_dataset(build_fixture_dataset(), config)


def test_pass_does_not_automatically_mean_golden():
    analysis = _analysis()
    passed = [q for q in analysis.qualities if q.verification.verdict == "PASS"]
    golden = [q for q in analysis.qualities if q.decision == "GOLDEN"]
    assert passed and golden
    assert len(golden) < len(passed)
    assert any(q.decision == "EXCLUDED" for q in passed)


def test_duplicates_constrained_to_representative():
    analysis = _analysis()
    by_id = {q.candidate_id: q for q in analysis.qualities}
    for group in analysis.duplicates.groups:
        if group.duplicate_type not in ("EXACT", "SEMANTIC"):
            continue
        golden_in_group = [c for c in group.member_ids if by_id[c].decision == "GOLDEN"]
        assert len(golden_in_group) <= 1, group.group_id
    # Representative ids are stable reporters (min id); the survivor (if any)
    # is the strongest-evidence member — both deterministic.


def test_contamination_prevents_golden():
    analysis = _analysis()
    for quality in analysis.qualities:
        if any(f.hard for f in quality.contamination_flags):
            assert quality.decision == "EXCLUDED"
            assert "CONTAMINATION" in quality.decision_reasons


def test_audit_failure_prevents_golden():
    from verified_data_factory.quality import record_audit_result

    records = build_fixture_dataset()
    baseline = analyze_dataset(records, QualityConfig(audit_rate=0.0))
    target = next(q.candidate_id for q in baseline.qualities if q.decision == "GOLDEN")
    full = analyze_dataset(records, QualityConfig(audit_rate=1.0))
    assert any(i.candidate_id == target for i in full.audit_sample.items)
    updated = record_audit_result(full.audit_sample, target, "FAIL", note="wrong grain")
    assert updated.items[0].status == "FAIL"
    second = analyze_dataset(
        records, QualityConfig(audit_rate=1.0), audit_overrides={target: "FAIL"}
    )
    by_id = {q.candidate_id: q for q in second.qualities}
    assert by_id[target].decision == "EXCLUDED"
    assert "AUDIT_FAIL" in by_id[target].decision_reasons


def test_inconclusive_never_golden():
    analysis = _analysis()
    for quality in analysis.qualities:
        if quality.decision == "GOLDEN":
            assert quality.verification.verdict == "PASS"
    # Truncated execution (valid task, inconclusive verification) stays inconclusive.
    truncated = next(
        q
        for q in analysis.qualities
        if q.verification.verdict == "INCONCLUSIVE" and q.task_quality.valid
    )
    assert truncated.decision == "INCONCLUSIVE"
    # Invalid tasks are excluded even when verification is inconclusive.
    invalid = next(q for q in analysis.qualities if not q.task_quality.valid)
    assert invalid.decision == "EXCLUDED"
    assert "TASK_INVALID" in invalid.decision_reasons


def test_fail_never_golden():
    analysis = _analysis()
    for quality in analysis.qualities:
        if quality.verification.verdict == "FAIL":
            assert quality.decision == "EXCLUDED"


def test_not_applicable_mutation_is_not_perfect_score():
    from tests.verify_testkit import (
        SimBackend,
        make_candidate,
        make_execution,
        make_task,
        oracle_rows,
    )
    from verified_data_factory.quality import analyze_record
    from verified_data_factory.quality.models import VerifiedRecord
    from verified_data_factory.verification import VerificationConfig, verify_candidate

    task = make_task("sql.dedup.latest")
    plain = make_candidate(task, "SELECT customer_id FROM events;")
    columns, rows = oracle_rows(task)
    plain_execution = make_execution(task, plain, rows, columns)
    verification = verify_candidate(
        task, plain, plain_execution, VerificationConfig(), SimBackend()
    )
    assert verification.mutation is not None and verification.mutation.applicable == 0
    quality = analyze_record(
        VerifiedRecord(
            task=task, candidate=plain, execution=plain_execution, verification=verification
        )
    )
    assert quality.verification.mutation_status == "NOT_APPLICABLE"
    assert quality.verification.mutation_score is None  # never treated as 1.0


def test_dataset_selection_deterministic_and_quota_bounded():
    first = _analysis()
    second = _analysis()
    assert [q.decision for q in first.qualities] == [q.decision for q in second.qualities]
    assert [q.decision_reasons for q in first.qualities] == [
        q.decision_reasons for q in second.qualities
    ]
    quota = _analysis(family_quotas={"simple_joins": 0})
    assert any("FAMILY_QUOTA" in q.decision_reasons for q in quota.qualities)
    assert not any(q.family == "simple_joins" and q.decision == "GOLDEN" for q in quota.qualities)


def test_evidence_preserved_through_selection():
    from tests.quality_dataset import build_fixture_dataset as _build

    records = _build()
    snapshots = {r.candidate.candidate_id: r.verification.model_dump_json() for r in records}
    analyze_dataset(records, QualityConfig(audit_rate=0.0))
    for record in records:
        assert record.verification.model_dump_json() == snapshots[record.candidate.candidate_id]


def test_require_strong_rejects_unknown_strength():
    from verified_data_factory.quality.golden import decide_record

    analysis = _analysis()
    quality = next(q for q in analysis.qualities if q.decision == "GOLDEN")
    unknown = quality.model_copy(
        update={
            "verification": quality.verification.model_copy(
                update={"verification_strength": "UNKNOWN"}
            ),
            "audit_required": False,
        }
    )
    decision, reasons = decide_record(unknown, QualityConfig(), {})
    assert decision == "EXCLUDED"
    assert reasons == ["STRONG_VERIFICATION_REQUIRED"]


def test_ineligible_duplicate_cannot_displace_eligible_member():
    from verified_data_factory.quality.golden import select_golden

    analysis = _analysis()
    choices = [q for q in analysis.qualities if q.decision == "GOLDEN"][:2]
    assert len(choices) == 2
    bad, good = sorted(choices, key=lambda q: q.candidate_id)
    bad = bad.model_copy(
        update={
            "semantic_duplicate_group": "test-eligible-group",
            "exact_duplicate_group": None,
            "verification": bad.verification.model_copy(
                update={"verdict": "FAIL", "failure_code": "TEST_FAILURE"}
            ),
            "audit_required": False,
        }
    )
    good = good.model_copy(
        update={
            "semantic_duplicate_group": "test-eligible-group",
            "exact_duplicate_group": None,
            "audit_required": False,
        }
    )
    result = {q.candidate_id: q for q in select_golden([bad, good], QualityConfig(), {})}
    assert result[bad.candidate_id].decision == "EXCLUDED"
    assert result[good.candidate_id].decision == "GOLDEN"


def test_at_most_one_golden_per_task():
    analysis = _analysis()
    counts: dict[str, int] = {}
    for quality in analysis.qualities:
        if quality.decision == "GOLDEN":
            counts[quality.task_id] = counts.get(quality.task_id, 0) + 1
    assert counts
    assert all(count <= 1 for count in counts.values())
