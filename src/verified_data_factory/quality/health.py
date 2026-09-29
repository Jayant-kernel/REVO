"""Dataset health report builder (Phase 5).

Multi-dimensional aggregates with counts and rates — deliberately no
single magic score. Every section derives from RecordQuality evidence,
so each exclusion stays explainable through decision_reasons.
"""

from __future__ import annotations

from collections import Counter

from .config import QualityConfig
from .models import (
    QUALITY_ENGINE_VERSION,
    AuditSample,
    ContaminationReport,
    CoverageReport,
    DatasetHealthReport,
    DifficultyReport,
    DiversityReport,
    DuplicateReport,
    FailureBreakdown,
    RecordQuality,
)


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def build_health_report(
    qualities: list[RecordQuality],
    duplicates: DuplicateReport,
    diversity: DiversityReport,
    coverage: CoverageReport,
    difficulty: DifficultyReport,
    contamination: ContaminationReport,
    audit_sample: AuditSample,
    config: QualityConfig,
) -> DatasetHealthReport:
    """Aggregate record evidence into the authoritative health report."""
    total = len(qualities)
    golden = [q for q in qualities if q.decision == "GOLDEN"]
    excluded = [q for q in qualities if q.decision == "EXCLUDED"]
    inconclusive = [q for q in qualities if q.decision == "INCONCLUSIVE"]
    audit_required = [q for q in qualities if q.decision == "AUDIT_REQUIRED"]

    passed = [q for q in qualities if q.verification.verdict == "PASS"]
    strong = [q for q in passed if q.verification.verification_strength == "STRONG"]
    weak = [q for q in passed if q.verification.verification_strength == "WEAK"]
    scored = [
        q.verification.mutation_score for q in passed if q.verification.mutation_score is not None
    ]
    hidden_ok = [q for q in passed if q.verification.hidden_tests_pass]
    prop_ok = [q for q in passed if q.verification.property_tests_pass]
    meta_ok = [q for q in passed if q.verification.metamorphic_tests_pass]

    task_valid = [q for q in qualities if q.task_quality.valid]
    ambiguous = [q for q in qualities if q.task_quality.ambiguity_flags]
    sem_complete = [q for q in qualities if q.task_quality.semantic_completeness_rate >= 1.0]
    schema_ok = [q for q in qualities if q.task_quality.schema_consistent]

    exact_members = sum(len(g.member_ids) for g in duplicates.groups if g.duplicate_type == "EXACT")
    structural_members = sum(
        len(g.member_ids) for g in duplicates.groups if g.duplicate_type == "STRUCTURAL"
    )
    semantic_members = sum(
        len(g.member_ids) for g in duplicates.groups if g.duplicate_type == "SEMANTIC"
    )

    audited = [i for i in audit_sample.items if i.result is not None]
    audit_failed = [i for i in audited if i.result == "FAIL"]

    reasons: Counter[str] = Counter()
    for quality in qualities:
        for reason in quality.decision_reasons:
            reasons[reason] += 1

    golden_families: Counter[str] = Counter(q.family for q in golden)
    golden_difficulties: Counter[str] = Counter(str(q.difficulty) for q in golden)

    return DatasetHealthReport(
        quality_engine_version=QUALITY_ENGINE_VERSION,
        quality_config_version=config.config_version,
        selection_seed=config.selection_seed,
        production={
            "candidate_count": float(total),
            "verified_count": float(len(passed)),
            "golden_count": float(len(golden)),
            "golden_yield": _rate(len(golden), total),
            "excluded_count": float(len(excluded)),
            "inconclusive_count": float(len(inconclusive)),
        },
        correctness={
            "verification_pass_rate": _rate(len(passed), total),
            "hidden_pass_rate": _rate(len(hidden_ok), total),
            "property_pass_rate": _rate(len(prop_ok), total),
            "metamorphic_pass_rate": _rate(len(meta_ok), total),
            "mutation_score_mean": sum(scored) / len(scored) if scored else 0.0,
            "mutation_scored_share": _rate(len(scored), total),
            "strong_verification_rate": _rate(len(strong), total),
            "weak_verification_rate": _rate(len(weak), total),
        },
        task_health={
            "task_validity_rate": _rate(len(task_valid), total),
            "ambiguity_rate": _rate(len(ambiguous), total),
            "semantic_completeness_rate": _rate(len(sem_complete), total),
            "schema_consistency_rate": _rate(len(schema_ok), total),
            "edge_case_coverage_rate": (
                sum(q.task_quality.edge_case_coverage_rate for q in qualities) / total
                if total
                else 0.0
            ),
        },
        duplicates={
            "exact_duplicate_rate": _rate(exact_members, total),
            "structural_duplicate_rate": _rate(structural_members, total),
            "semantic_duplicate_rate": _rate(semantic_members, total),
            "duplicate_groups": float(len(duplicates.groups)),
        },
        diversity=diversity,
        coverage=coverage,
        difficulty=difficulty,
        reliability={
            "verification_inconclusive_rate": _rate(
                sum(1 for q in qualities if q.verification.verdict == "INCONCLUSIVE"), total
            ),
            "execution_failure_rate": _rate(
                sum(1 for q in qualities if q.verification.failure_code == "EXECUTION_FAILED"),
                total,
            ),
            "oracle_failure_rate": _rate(
                sum(
                    1 for q in qualities if (q.verification.failure_code or "").startswith("ORACLE")
                ),
                total,
            ),
            "audit_failure_rate": _rate(len(audit_failed), len(audited)),
        },
        contamination={
            "flagged_count": contamination.flagged_count,
            "contaminated_rate": contamination.contaminated_rate,
            "split_overlap_count": contamination.split_overlap_count,
            "flags_by_type": dict(contamination.flags_by_type),
        },
        golden={
            "golden_count": float(len(golden)),
            "golden_yield": _rate(len(golden), total),
        },
        golden_family_distribution={k: float(v) for k, v in sorted(golden_families.items())},
        golden_difficulty_distribution={
            k: float(v) for k, v in sorted(golden_difficulties.items())
        },
        golden_coverage_families=float(len({q.family for q in golden})),
        failures=FailureBreakdown(
            candidates=total,
            verified_pass=len(passed),
            golden=len(golden),
            excluded=len(excluded),
            inconclusive=len(inconclusive),
            audit_required=len(audit_required),
            by_reason=dict(sorted(reasons.items())),
        ),
    )
