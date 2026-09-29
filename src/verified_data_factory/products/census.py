"""Corpus census and machine-generated audit reports (§6, §10 remediation).

The census aggregates record-level evidence deterministically — it
reproduces empirical findings (e.g. 232/232 STRONG) from the data
rather than substituting aggregated claims. The audit report renders
factual readiness statuses; it never produces a subjective score.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .diversity import build_diversity_report
from .errors import ProductIOError
from .models import PRODUCT_SCHEMA_VERSION, AuditReport, CensusReport
from .row_manifest import RowManifest

__all__ = [
    "build_audit_report",
    "build_census",
    "render_audit_markdown",
    "write_json_payload",
]


def _scored_at_threshold(golden: dict[str, Any], mutation_min_score: float) -> bool:
    verification = golden.get("verification", {})
    if not isinstance(verification, dict):
        return False
    mutation = verification.get("mutation", {})
    if not isinstance(mutation, dict):
        return False
    score = mutation.get("mutation_score")
    return score is not None and score >= mutation_min_score


def build_census(
    *,
    golden_records: list[dict[str, Any]],
    quality_by_id: dict[str, dict[str, Any]],
    health: dict[str, Any] | None = None,
    duplicates: dict[str, Any] | None = None,
    row_manifest: list[RowManifest] | None = None,
    quarantined_ids: set[str] | None = None,
    justifications: dict[str, str] | None = None,
    governance_unresolved_count: int = 0,
    mutation_min_score: float = 0.9,
) -> CensusReport:
    """Aggregate record-level evidence into a deterministic census."""
    health = health or {}
    duplicates = duplicates or {}
    quarantined_ids = quarantined_ids or set()
    justifications = justifications or {}
    n = len(golden_records)

    strengths: Counter[str] = Counter()
    scores: Counter[str] = Counter()
    applicable_histogram: Counter[str] = Counter()
    zero_ids: list[str] = []
    unjustified = 0
    for golden in golden_records:
        candidate_id = str(golden.get("candidate_id", ""))
        verification = (
            golden.get("verification", {}) if isinstance(golden.get("verification"), dict) else {}
        )
        strength = str(verification.get("verification_strength", "UNKNOWN"))
        strengths[strength] += 1
        mutation = (
            verification.get("mutation", {})
            if isinstance(verification.get("mutation"), dict)
            else {}
        )
        score = mutation.get("mutation_score")
        scores["1.0" if score == 1.0 else ("null" if score is None else str(score))] += 1
        applicable = int(mutation.get("applicable", 0) or 0)
        applicable_histogram[str(applicable)] += 1
        if applicable == 0:
            zero_ids.append(candidate_id)
            justification = justifications.get(candidate_id, "")
            quality = quality_by_id.get(candidate_id, {})
            if (
                not justification.strip()
                and not str(quality.get("mutation_justification", "")).strip()
            ):
                unjustified += 1

    families: Counter[str] = Counter()
    for golden in golden_records:
        task = golden.get("task", {})
        families[str(task.get("family", "unknown") if isinstance(task, dict) else "unknown")] += 1

    contamination_by_type: Counter[str] = Counter()
    hard_count = 0
    for candidate_id in [str(g.get("candidate_id", "")) for g in golden_records]:
        for flag in quality_by_id.get(candidate_id, {}).get("contamination_flags", []) or []:
            if isinstance(flag, dict):
                contamination_by_type[str(flag.get("flag_type", "UNKNOWN"))] += 1
                hard_count += int(bool(flag.get("hard")))

    run_counts: Counter[str] = Counter()
    revision_counts: Counter[str] = Counter()
    template_counts: Counter[str] = Counter()
    prompt_counts: Counter[str] = Counter()
    for row in row_manifest or []:
        run_counts[row.generation_run_id or "UNKNOWN"] += 1
        revision_counts[f"{row.model_name}@{row.model_revision}"] += 1
        template_counts[f"{row.template_id}v{row.template_version}"] += 1
        prompt_counts[row.prompt_version or "UNKNOWN"] += 1
    provenance_missing: Counter[str] = Counter()
    complete = 0
    for row in row_manifest or []:
        missing = [
            field
            for field in (
                "task_id",
                "family",
                "template_id",
                "model_name",
                "candidate_id",
                "dataset_snapshot_id",
            )
            if not getattr(row, field) or getattr(row, field) == "unknown"
        ]
        if missing:
            for field in missing:
                provenance_missing[field] += 1
        else:
            complete += 1

    groups = duplicates.get("groups", []) if isinstance(duplicates.get("groups"), list) else []
    exact_groups = sum(
        1 for g in groups if isinstance(g, dict) and g.get("duplicate_type") == "EXACT"
    )
    semantic_groups = sum(
        1 for g in groups if isinstance(g, dict) and g.get("duplicate_type") == "SEMANTIC"
    )
    population_rates: dict[str, float] = {}
    health_duplicates = (
        health.get("duplicates", {}) if isinstance(health.get("duplicates"), dict) else {}
    )
    for key in ("exact_duplicate_rate", "structural_duplicate_rate", "semantic_duplicate_rate"):
        value = health_duplicates.get(key)
        if isinstance(value, (int, float)):
            population_rates[key] = float(value)

    all_strong = n > 0 and set(strengths) == {"STRONG"}
    all_scored = n > 0 and all(_scored_at_threshold(g, mutation_min_score) for g in golden_records)
    return CensusReport(
        record_count=n,
        strength_distribution=dict(sorted(strengths.items())),
        mutation_score_distribution=dict(sorted(scores.items())),
        mutation_applicable_histogram=dict(sorted(applicable_histogram.items())),
        zero_applicable_count=len(zero_ids),
        zero_applicable_ids=sorted(zero_ids),
        unjustified_zero_applicable_count=unjustified,
        family_counts=dict(sorted(families.items())),
        generation_run_counts=dict(sorted(run_counts.items())),
        model_revision_counts=dict(sorted(revision_counts.items())),
        template_version_counts=dict(sorted(template_counts.items())),
        prompt_version_counts=dict(sorted(prompt_counts.items())),
        contamination_by_type=dict(sorted(contamination_by_type.items())),
        contamination_hard_count=hard_count,
        quarantine_count=len([i for i in quarantined_ids if i]),
        quarantined_ids=sorted(quarantined_ids),
        governance_unresolved_count=governance_unresolved_count,
        provenance_complete_count=complete,
        provenance_missing_fields=dict(sorted(provenance_missing.items())),
        duplicate_exact_groups=exact_groups,
        duplicate_semantic_groups=semantic_groups,
        population_duplicate_rates=population_rates,
        diversity=build_diversity_report(
            golden_records=golden_records, quality_by_id=quality_by_id, duplicates=duplicates
        ),
        all_strong=all_strong,
        all_scored_at_threshold=all_scored,
        schema_version=PRODUCT_SCHEMA_VERSION,
    )


def build_audit_report(
    *,
    census: CensusReport,
    supply_chain: dict[str, Any] | None = None,
    quarantine_entries: list[dict[str, Any]] | None = None,
    release_manifest: dict[str, Any] | None = None,
    corpus_extra: dict[str, Any] | None = None,
) -> AuditReport:
    """Render factual readiness statuses from census + governance evidence."""
    supply_chain = supply_chain or {}
    quarantine_entries = quarantine_entries or []
    release_manifest = release_manifest or {}

    corpus = {
        "record_count": census.record_count,
        "family_counts": dict(census.family_counts),
        "families_represented": len(census.family_counts),
        **(corpus_extra or {}),
    }
    verification = {
        "strength_distribution": dict(census.strength_distribution),
        "mutation_score_distribution": dict(census.mutation_score_distribution),
        "zero_applicable_count": census.zero_applicable_count,
        "zero_applicable_ids": list(census.zero_applicable_ids),
        "unjustified_zero_applicable_count": census.unjustified_zero_applicable_count,
        "all_strong": census.all_strong,
        "all_scored_at_threshold": census.all_scored_at_threshold,
    }
    governance = {
        "governance_status": supply_chain.get("governance_status", "UNKNOWN"),
        "commercially_cleared": supply_chain.get("commercially_cleared", False),
        "clearance_reasons": list(supply_chain.get("clearance_reasons", [])),
        "unresolved_count": census.governance_unresolved_count,
    }
    provenance = {
        "complete_count": census.provenance_complete_count,
        "record_count": census.record_count,
        "missing_fields": dict(census.provenance_missing_fields),
    }
    diversity = census.diversity.model_dump(mode="json") if census.diversity else {}
    quarantine = {
        "count": census.quarantine_count,
        "ids": list(census.quarantined_ids),
        "entries": list(quarantine_entries),
    }

    technically_verified = (
        census.all_strong
        and census.all_scored_at_threshold
        and census.unjustified_zero_applicable_count == 0
        and census.record_count > 0
    )
    provenance_complete = (
        census.record_count > 0 and census.provenance_complete_count == census.record_count
    )
    governance_clear = bool(supply_chain.get("commercially_cleared", False))
    commercial_eligible = technically_verified and provenance_complete and governance_clear
    readiness = {
        "technical": "TECHNICALLY_VERIFIED" if technically_verified else "NEEDS_REVIEW",
        "provenance": "PROVENANCE_COMPLETE" if provenance_complete else "PROVENANCE_INCOMPLETE",
        "governance": "GOVERNANCE_CLEAR" if governance_clear else "GOVERNANCE_REVIEW_REQUIRED",
        "commercial": "COMMERCIAL_ELIGIBLE"
        if commercial_eligible
        else "COMMERCIAL_RELEASE_BLOCKED",
        "overall": "READY_FOR_REVIEW" if commercial_eligible else "NOT_READY",
        "release_id": str(release_manifest.get("release_id", "")),
    }
    return AuditReport(
        corpus=corpus,
        verification=verification,
        governance=governance,
        provenance=provenance,
        diversity=diversity,
        quarantine=quarantine,
        readiness=readiness,
        schema_version=PRODUCT_SCHEMA_VERSION,
    )


def write_json_payload(payload: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        raise ProductIOError(f"cannot write {path}: {exc}") from exc
    return path


def render_audit_markdown(report: AuditReport) -> str:
    """Human-readable rendering of the machine-generated audit report."""
    lines = ["# Audit report (machine-generated)", ""]
    sections = [
        ("1. Corpus", report.corpus),
        ("2. Verification", report.verification),
        ("3. Governance", report.governance),
        ("4. Provenance", report.provenance),
        ("6. Quarantine", report.quarantine),
    ]
    for title, payload in sections:
        lines.append(f"## Section {title}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(payload, indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")
    lines.append("## Section 5. Diversity (summary)")
    lines.append("")
    diversity = report.diversity
    for key in (
        "record_count",
        "instruction_unique_normalized",
        "instruction_unique_ratio",
        "instruction_top_share",
        "sql_unique_normalized",
        "sql_unique_ratio",
        "schema_identities",
        "semantic_groups",
        "exact_groups",
    ):
        lines.append(f"- {key}: {diversity.get(key, 'UNKNOWN')}")
    lines.append("")
    lines.append("## Section 7. Release readiness")
    lines.append("")
    for key, value in report.readiness.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    return "\n".join(lines)
