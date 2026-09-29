"""Risk-based human audit sampling (Phase 5).

Samples a deterministic subset for review: highest-risk records first,
plus a seeded random slice so low-risk records can still be sampled.
Repeated runs with identical inputs return identical samples. No UI;
JSONL-friendly items with PENDING/PASS/FAIL/UNCLEAR results.
"""

from __future__ import annotations

import logging
import random
from typing import Any

from .config import QualityConfig
from .models import AuditItem, AuditSample, AuditStatus, RecordQuality, RiskBand

logger = logging.getLogger(__name__)


def risk_signals(quality: RecordQuality, context: dict[str, Any]) -> tuple[int, list[str]]:
    """Score one record against configured risk weights. Deterministic."""
    weights = context["weights"]
    score = 0
    reasons: list[str] = []

    def add(key: str, reason: str, condition: bool) -> None:
        nonlocal score
        if condition:
            score += int(weights.get(key, 0))
            reasons.append(reason)

    add("ambiguity", "ambiguous-task", bool(quality.task_quality.ambiguity_flags))
    add(
        "weak_verification",
        "weak-verification",
        quality.verification.verification_strength == "WEAK",
    )
    add(
        "mutation_survived",
        "mutation-survived",
        (quality.verification.mutation_score or 1.0) < 1.0
        and quality.verification.mutation_status == "SCORED",
    )
    add(
        "contamination_soft",
        "contamination-flag",
        any(not f.hard for f in quality.contamination_flags),
    )
    add(
        "rare_family",
        "rare-family",
        context["family_share"].get(quality.family, 1.0) < context["rare_threshold"],
    )
    add(
        "rare_edge_case",
        "rare-edge-case",
        any(e in context["rare_edges"] for e in quality.task_quality.edge_cases_present),
    )
    add(
        "duplicate_non_representative",
        "duplicate-non-representative",
        bool(quality.semantic_duplicate_group or quality.exact_duplicate_group)
        and not quality.is_duplicate_representative,
    )
    add(
        "first_of_template",
        "first-of-template",
        context["first_of_template"].get(
            (quality.template_id, quality.template_version), quality.candidate_id
        )
        == quality.candidate_id
        and context["template_counts"].get((quality.template_id, quality.template_version), 0) > 1,
    )
    return score, sorted(reasons)


def build_audit_context(qualities: list[RecordQuality], config: QualityConfig) -> dict[str, Any]:
    """Dataset frequencies needed for relative risk (rare family/edge)."""
    total = max(1, len(qualities))
    family_counts: dict[str, int] = {}
    edge_counts: dict[str, int] = {}
    template_counts: dict[tuple[str, int], int] = {}
    first_of_template: dict[tuple[str, int], str] = {}
    for quality in sorted(qualities, key=lambda q: q.candidate_id):
        family_counts[quality.family] = family_counts.get(quality.family, 0) + 1
        template_counts[(quality.template_id, quality.template_version)] = (
            template_counts.get((quality.template_id, quality.template_version), 0) + 1
        )
        first_of_template.setdefault(
            (quality.template_id, quality.template_version), quality.candidate_id
        )
        for edge in quality.task_quality.edge_cases_present:
            edge_counts[edge] = edge_counts.get(edge, 0) + 1
    rare_edges = {e for e, c in edge_counts.items() if c / total < config.rare_family_threshold}
    return {
        "weights": config.risk_weights,
        "family_share": {f: c / total for f, c in family_counts.items()},
        "rare_threshold": config.rare_family_threshold,
        "rare_edges": rare_edges,
        "first_of_template": first_of_template,
        "template_counts": template_counts,
    }


def _risk_band(score: int, config: QualityConfig) -> RiskBand:
    if score >= config.risk_threshold_high:
        return "HIGH"
    if score >= config.risk_threshold_medium:
        return "MEDIUM"
    return "LOW"


def sample_audit(qualities: list[RecordQuality], config: QualityConfig) -> AuditSample:
    """Deterministic risk-based sample (no timestamps in items)."""
    context = build_audit_context(qualities, config)
    scored = [
        (risk_signals(q, context), q) for q in sorted(qualities, key=lambda q: q.candidate_id)
    ]
    ranked = sorted(scored, key=lambda pair: (-pair[0][0], pair[1].candidate_id))
    if not ranked or config.audit_rate <= 0:
        return AuditSample(items=[], selection_seed=config.audit_seed, sampled_count=0)
    target = min(len(ranked), max(1, round(len(ranked) * config.audit_rate)))
    high_risk = [pair for pair in ranked if pair[0][0] >= config.risk_threshold_medium]
    chosen = list(high_risk[:target])
    if len(chosen) < target:
        chosen_ids = {q.candidate_id for _, q in chosen}
        rest = [pair for pair in ranked if pair[1].candidate_id not in chosen_ids]
        rng = random.Random(config.audit_seed)
        rng.shuffle(rest)
        chosen.extend(rest[: target - len(chosen)])
    items = [
        AuditItem(
            audit_id=f"audit-{quality.candidate_id}",
            candidate_id=quality.candidate_id,
            task_id=quality.task_id,
            risk_score=score,
            risk_band=_risk_band(score, config),
            reasons=reasons,
        )
        for (score, reasons), quality in sorted(chosen, key=lambda pair: pair[1].candidate_id)
    ]
    logger.info(
        "audit sampling complete",
        extra={"sampled": len(items), "of": len(qualities)},
    )
    return AuditSample(items=items, selection_seed=config.audit_seed, sampled_count=len(items))


def record_audit_result(
    sample: AuditSample, candidate_id: str, result: AuditStatus, note: str = ""
) -> AuditSample:
    """Record a human decision (returns an updated sample; no timestamps)."""
    if result not in ("PASS", "FAIL", "UNCLEAR"):
        raise ValueError(f"result must be PASS/FAIL/UNCLEAR, got {result!r}")
    items = []
    found = False
    for item in sample.items:
        if item.candidate_id == candidate_id:
            items.append(item.model_copy(update={"status": result, "result": result, "note": note}))
            found = True
        else:
            items.append(item)
    if not found:
        raise ValueError(f"candidate {candidate_id!r} not in audit sample")
    return AuditSample(
        items=items, selection_seed=sample.selection_seed, sampled_count=sample.sampled_count
    )
