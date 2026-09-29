"""Per-record quality assembly (Phase 5).

Restates Phase 4 evidence (never recomputes verdicts) and attaches
task-quality evidence. Dataset-level fields (duplicates, contamination,
audit, decision) are filled by later stages, never here.
"""

from __future__ import annotations

from .models import RecordQuality, TaskQualityEvidence, VerificationSummary, VerifiedRecord
from .task_quality import assess_task_quality


def summarize_verification(record: VerifiedRecord) -> VerificationSummary:
    """Restate Phase 4 evidence for qualification (no reinterpretation)."""
    verification = record.verification
    comparison_match = bool(verification.comparison is not None and verification.comparison.match)
    hidden = verification.hidden
    hidden_pass = bool(
        hidden is not None and hidden.total > 0 and hidden.failed == 0 and hidden.inconclusive == 0
    )
    properties = verification.properties
    properties_pass = bool(properties is not None and properties.failed == 0)
    metamorphic = verification.metamorphic
    metamorphic_pass = bool(metamorphic is not None and metamorphic.failed == 0)
    mutation = verification.mutation
    applicable = int(mutation.applicable) if mutation is not None else 0
    score = (
        float(mutation.mutation_score)
        if mutation is not None and mutation.mutation_score is not None
        else None
    )
    return VerificationSummary(
        verdict=str(verification.verdict),
        verification_strength=str(verification.verification_strength),
        failure_code=verification.failure_code,
        original_execution_pass=comparison_match,
        hidden_tests_pass=hidden_pass,
        hidden_failed=int(hidden.failed) if hidden is not None else 0,
        property_tests_pass=properties_pass,
        metamorphic_tests_pass=metamorphic_pass,
        mutation_score=score,
        mutation_applicable=applicable,
        mutation_status="SCORED" if score is not None else "NOT_APPLICABLE",
    )


def analyze_record(record: VerifiedRecord) -> RecordQuality:
    """Build per-record quality evidence (dataset fields left empty)."""
    task_quality: TaskQualityEvidence = assess_task_quality(record.task)
    summary = summarize_verification(record)
    return RecordQuality(
        candidate_id=record.candidate.candidate_id,
        task_id=record.task.task_id,
        template_id=record.task.template_id,
        template_version=record.task.template_version,
        family=record.task.family,
        seed=record.task.seed,
        difficulty=int(record.task.difficulty),
        role=record.role,
        task_quality=task_quality,
        verification=summary,
    )
