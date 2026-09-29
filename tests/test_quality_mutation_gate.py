"""Zero-applicable-mutant gate tests (§1 remediation).

NOT_APPLICABLE is preserved as a distinct state: it never becomes a
passing score, and Golden requires an explicit persisted justification.
"""

from tests.quality_dataset import build_fixture_dataset
from verified_data_factory.quality import (
    QualityConfig,
    analyze_dataset,
    decide_record,
    mutation_evidence_state,
    select_golden,
)


def _golden_quality():
    analysis = analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=0.0))
    golden = [q for q in analysis.qualities if q.decision == "GOLDEN"]
    assert golden, "fixture must contain golden material"
    return golden[0], analysis


def _zero_applicable(quality):
    verification = quality.verification.model_copy(
        update={
            "mutation_status": "NOT_APPLICABLE",
            "mutation_applicable": 0,
            "mutation_score": None,
        }
    )
    return quality.model_copy(update={"verification": verification})


def test_zero_applicable_without_justification_excluded():
    quality, _ = _golden_quality()
    candidate = _zero_applicable(quality)
    decision, reasons = decide_record(candidate, QualityConfig(audit_rate=0.0), {})
    assert decision == "EXCLUDED"
    assert reasons == ["MUTATION_JUSTIFICATION_REQUIRED"]


def test_zero_applicable_with_dict_justification_permitted():
    quality, _ = _golden_quality()
    candidate = _zero_applicable(quality)
    decided = select_golden(
        [candidate],
        QualityConfig(audit_rate=0.0),
        {},
        justifications={candidate.candidate_id: "single-row aggregate admits no valid mutant"},
    )
    assert decided[0].decision == "GOLDEN"


def test_zero_applicable_with_field_justification_permitted():
    quality, _ = _golden_quality()
    candidate = _zero_applicable(quality).model_copy(
        update={"mutation_justification": "auditor-confirmed: no valid mutant for this shape"}
    )
    decision, _ = decide_record(candidate, QualityConfig(audit_rate=0.0), {})
    assert decision == "GOLDEN"


def test_blank_justification_rejected():
    quality, _ = _golden_quality()
    candidate = _zero_applicable(quality)
    decision, _ = decide_record(
        candidate, QualityConfig(audit_rate=0.0), {}, justifications={candidate.candidate_id: "   "}
    )
    assert decision == "EXCLUDED"


def test_scored_below_threshold_still_rejected():
    quality, _ = _golden_quality()
    verification = quality.verification.model_copy(
        update={"mutation_status": "SCORED", "mutation_applicable": 3, "mutation_score": 0.5}
    )
    candidate = quality.model_copy(update={"verification": verification})
    decision, reasons = decide_record(candidate, QualityConfig(audit_rate=0.0), {})
    assert decision == "EXCLUDED"
    assert reasons == ["MUTATION_THRESHOLD"]


def test_scored_above_threshold_normal_path():
    quality, analysis = _golden_quality()
    assert quality.verification.mutation_status == "SCORED"
    assert (quality.verification.mutation_score or 0.0) >= 0.9
    by_id = {q.candidate_id: q for q in analysis.qualities}
    assert by_id[quality.candidate_id].decision == "GOLDEN"


def test_fixture_golden_set_unchanged_without_justifications():
    before = analyze_dataset(build_fixture_dataset(), QualityConfig(audit_rate=0.0))
    after = analyze_dataset(
        build_fixture_dataset(), QualityConfig(audit_rate=0.0), justifications={}
    )
    assert [q.decision for q in before.qualities] == [q.decision for q in after.qualities]


def test_zero_applicable_never_serialized_as_one():
    """A real in-pipeline NOT_APPLICABLE record exports null score, never 1.0."""
    from verified_data_factory.quality import golden_record_for

    records = build_fixture_dataset()
    analysis = analyze_dataset(records, QualityConfig(audit_rate=0.0))
    candidate = next(
        q for q in analysis.qualities if q.verification.mutation_status == "NOT_APPLICABLE"
    )
    by_record = {r.candidate.candidate_id: r for r in records}
    blob = golden_record_for(candidate, by_record[candidate.candidate_id]).model_dump(mode="json")
    exported = blob["verification"]["mutation"]
    assert exported is None or exported.get("mutation_score") is None
    assert exported is None or exported.get("mutation_score") != 1.0


def test_mutation_evidence_states():
    quality, _ = _golden_quality()
    assert mutation_evidence_state(quality) == "SCORED"
    zero = _zero_applicable(quality)
    assert mutation_evidence_state(zero) == "UNJUSTIFIED"
    assert mutation_evidence_state(zero, "genuine reason") == "JUSTIFIED"
