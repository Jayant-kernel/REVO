"""Golden selection (Phase 5).

Two stages: per-record hard gates (evidence-driven, explainable), then
dataset-aware selection (dedup representatives, family quotas) applied
deterministically over sorted records. PASS is never sufficient alone.
"""

from __future__ import annotations

import logging

from .config import QualityConfig
from .models import GoldenDecision, RecordQuality

logger = logging.getLogger(__name__)


def decide_record(
    quality: RecordQuality,
    config: QualityConfig,
    audit_results: dict[str, str],
    justifications: dict[str, str] | None = None,
) -> tuple[GoldenDecision, list[str]]:
    """Per-record gates. Returns (decision, reasons); never mutates input.

    ``justifications`` maps candidate_id → explicit auditor text explaining
    why the mutation suite genuinely cannot apply. A zero-applicable record
    without one is EXCLUDED (MUTATION_JUSTIFICATION_REQUIRED): the
    NOT_APPLICABLE state is preserved, never converted into a passing score.
    """
    verification = quality.verification
    task_quality = quality.task_quality

    if not task_quality.valid:
        return "EXCLUDED", ["TASK_INVALID", *task_quality.validation_errors[:3]]
    if verification.verdict == "FAIL":
        code = verification.failure_code or "VERIFICATION_FAIL"
        return "EXCLUDED", ["VERIFICATION_FAIL", code]
    if verification.verdict == "INCONCLUSIVE":
        return "INCONCLUSIVE", ["VERIFICATION_INCONCLUSIVE", verification.failure_code or "UNKNOWN"]
    if not verification.original_execution_pass:
        return "EXCLUDED", ["ORIGINAL_EXECUTION_FAIL"]
    if not verification.hidden_tests_pass:
        return "EXCLUDED", ["HIDDEN_TESTS_FAIL"]
    if not verification.property_tests_pass:
        return "EXCLUDED", ["PROPERTY_TESTS_FAIL"]
    if not verification.metamorphic_tests_pass:
        return "EXCLUDED", ["METAMORPHIC_TESTS_FAIL"]
    if config.require_strong_verification and verification.verification_strength != "STRONG":
        return "EXCLUDED", ["STRONG_VERIFICATION_REQUIRED"]
    if (
        verification.mutation_status == "SCORED"
        and (verification.mutation_score or 0.0) < config.mutation_min_score
    ):
        return "EXCLUDED", ["MUTATION_THRESHOLD"]
    if verification.mutation_status == "NOT_APPLICABLE" or verification.mutation_applicable == 0:
        justification = (justifications or {}).get(quality.candidate_id, "")
        if not justification.strip() and not quality.mutation_justification.strip():
            return "EXCLUDED", ["MUTATION_JUSTIFICATION_REQUIRED"]
    hard_contamination = sorted(f.flag_type for f in quality.contamination_flags if f.hard)
    if hard_contamination:
        return "EXCLUDED", ["CONTAMINATION", *hard_contamination[:3]]
    audit_result = audit_results.get(quality.candidate_id)
    if audit_result == "FAIL":
        return "EXCLUDED", ["AUDIT_FAIL"]
    if quality.audit_required and audit_result != "PASS":
        return "AUDIT_REQUIRED", ["AUDIT_PENDING"]
    return "GOLDEN", []


def _strength_rank(quality: RecordQuality) -> int:
    return {"STRONG": 0, "UNKNOWN": 1, "WEAK": 2}.get(quality.verification.verification_strength, 3)


def mutation_evidence_state(quality: RecordQuality, justification: str = "") -> str:
    """Classify mutation evidence without judging it: SCORED, JUSTIFIED, or UNJUSTIFIED."""
    verification = quality.verification
    if verification.mutation_status == "SCORED":
        return "SCORED"
    if justification.strip() or quality.mutation_justification.strip():
        return "JUSTIFIED"
    return "UNJUSTIFIED"


def select_golden(
    qualities: list[RecordQuality],
    config: QualityConfig,
    audit_results: dict[str, str],
    justifications: dict[str, str] | None = None,
    quarantined: dict[str, str] | None = None,
) -> list[RecordQuality]:
    """Dataset-aware selection: gates, then dedup + quotas, deterministically.

    ``quarantined`` maps candidate_id → quarantine reason. Quarantined
    records are demoted before dedup/quotas run, so they can never
    displace a healthy representative.
    """
    quarantined = quarantined or {}
    decided: list[RecordQuality] = []
    for quality in sorted(qualities, key=lambda q: q.candidate_id):
        decision, reasons = decide_record(quality, config, audit_results, justifications)
        if quality.candidate_id in quarantined:
            decision, reasons = "EXCLUDED", [*reasons, "QUARANTINED"]
        decided.append(
            quality.model_copy(update={"decision": decision, "decision_reasons": reasons})
        )

    by_id = {q.candidate_id: q for q in decided}
    # Deduplication: only the representative of each semantic/exact group
    # survives, preferring stronger evidence deterministically.
    for group_attr in ("semantic_duplicate_group", "exact_duplicate_group"):
        groups: dict[str, list[str]] = {}
        for quality in decided:
            group = getattr(quality, group_attr)
            if group:
                groups.setdefault(group, []).append(quality.candidate_id)
        for members in groups.values():
            eligible = [cid for cid in members if by_id[cid].decision == "GOLDEN"]
            if len(eligible) < 2:
                continue
            ranked = sorted(
                eligible,
                key=lambda cid: (
                    _strength_rank(by_id[cid]),
                    -(by_id[cid].verification.mutation_score or 0.0),
                    cid,
                ),
            )
            for loser in ranked[1:]:
                current = by_id[loser]
                if current.decision == "GOLDEN":
                    reasons = [
                        *current.decision_reasons,
                        "SEMANTIC_DUPLICATE" if "semantic" in group_attr else "EXACT_DUPLICATE",
                    ]
                    by_id[loser] = current.model_copy(
                        update={"decision": "EXCLUDED", "decision_reasons": reasons}
                    )

    # Family quotas: keep the strongest-first prefix per family.
    if config.family_quotas or config.max_family_share:
        families: dict[str, list[str]] = {}
        for quality in by_id.values():
            if quality.decision == "GOLDEN":
                families.setdefault(quality.family, []).append(quality.candidate_id)
        total_golden = sum(len(v) for v in families.values())
        for family, members in families.items():
            quota = config.family_quotas.get(family)
            if quota is None and config.max_family_share is not None:
                quota = max(1, int(total_golden * config.max_family_share))
            if quota is None:
                continue
            ranked = sorted(
                members,
                key=lambda cid: (
                    _strength_rank(by_id[cid]),
                    -(by_id[cid].verification.mutation_score or 0.0),
                    cid,
                ),
            )
            for loser in ranked[quota:]:
                current = by_id[loser]
                reasons = [*current.decision_reasons, "FAMILY_QUOTA"]
                by_id[loser] = current.model_copy(
                    update={"decision": "EXCLUDED", "decision_reasons": reasons}
                )

    ordered = [by_id[cid] for cid in sorted(by_id)]
    logger.info(
        "golden selection complete",
        extra={"golden": sum(1 for q in ordered if q.decision == "GOLDEN"), "of": len(ordered)},
    )
    return ordered
