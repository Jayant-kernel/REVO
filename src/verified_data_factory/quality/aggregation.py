"""Dataset aggregation pipeline (Phase 5).

Order follows the architecture: record evidence -> duplicates ->
diversity/coverage/difficulty (dataset context) -> contamination ->
audit sampling -> golden selection -> health report. Each stage is a
small pure function; this module only wires them.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from verified_data_factory.task_engine import canonical_task_dict

from .audit import record_audit_result, sample_audit
from .config import QualityConfig
from .contamination import analyze_contamination
from .coverage import compute_coverage
from .difficulty import analyze_difficulty
from .diversity import compute_diversity
from .duplicate_detection import detect_duplicates
from .golden import select_golden
from .health import build_health_report
from .models import (
    AuditSample,
    AuditStatus,
    ContaminationReport,
    CoverageReport,
    DatasetHealthReport,
    DifficultyReport,
    DiversityReport,
    DuplicateReport,
    RecordQuality,
    VerifiedRecord,
)
from .record_quality import analyze_record

logger = logging.getLogger(__name__)


def _as_audit_status(result: str, candidate_id: str) -> AuditStatus:
    if result == "PASS":
        return "PASS"
    if result == "FAIL":
        return "FAIL"
    if result == "UNCLEAR":
        return "UNCLEAR"
    raise ValueError(f"bad audit override for {candidate_id!r}: {result!r}")


class DatasetAnalysis:
    """All Phase 5 outputs for one input collection (plain container)."""

    def __init__(
        self,
        records: list[VerifiedRecord],
        qualities: list[RecordQuality],
        duplicates: DuplicateReport,
        diversity: DiversityReport,
        coverage: CoverageReport,
        difficulty: DifficultyReport,
        contamination: ContaminationReport,
        audit_sample: AuditSample,
        health: DatasetHealthReport,
        config: QualityConfig,
    ) -> None:
        self.records = records
        self.qualities = qualities
        self.duplicates = duplicates
        self.diversity = diversity
        self.coverage = coverage
        self.difficulty = difficulty
        self.contamination = contamination
        self.audit_sample = audit_sample
        self.health = health
        self.config = config

    def golden(self) -> list[RecordQuality]:
        return [q for q in self.qualities if q.decision == "GOLDEN"]


def _side_inputs(records: list[VerifiedRecord]) -> dict[str, Any]:
    candidate_sql: dict[str, str] = {}
    canonical_tasks: dict[str, str] = {}
    schemas: dict[str, list[dict[str, Any]]] = {}
    fixture_counts: dict[str, str] = {}
    for record in records:
        cid = record.candidate.candidate_id
        candidate_sql[cid] = record.candidate.candidate_sql or ""
        canonical_tasks[cid] = json.dumps(
            canonical_task_dict(record.task), sort_keys=True, default=str
        )
        schemas[cid] = [t.model_dump(mode="json") for t in record.task.schema_]
        counts = sorted(f"{name}:{len(rows)}" for name, rows in sorted(record.task.tables.items()))
        fixture_counts[cid] = ",".join(counts)
    return {
        "candidate_sql": candidate_sql,
        "canonical_tasks": canonical_tasks,
        "schemas": schemas,
        "fixture_counts": fixture_counts,
    }


def analyze_dataset(
    records: list[VerifiedRecord],
    config: QualityConfig,
    audit_overrides: dict[str, str] | None = None,
    justifications: dict[str, str] | None = None,
    quarantined: dict[str, str] | None = None,
) -> DatasetAnalysis:
    """Run the full Phase 5 pipeline deterministically.

    ``justifications`` maps candidate_id → auditor text explaining why the
    mutation suite genuinely cannot apply; zero-applicable records without
    one cannot become Golden. ``quarantined`` maps candidate_id → reason
    and demotes records before dedup/quotas run.
    """
    logger.info("dataset analysis started", extra={"records": len(records)})
    sides = _side_inputs(records)
    qualities = [analyze_record(r) for r in sorted(records, key=lambda r: r.candidate.candidate_id)]

    duplicates = detect_duplicates(
        qualities,
        sides["candidate_sql"],
        sides["canonical_tasks"],
        sides["schemas"],
        sides["fixture_counts"],
    )
    dup_lookup: dict[str, dict[str, str]] = {}
    for group in duplicates.groups:
        for member in group.member_ids:
            dup_lookup.setdefault(member, {})[group.duplicate_type.lower()] = group.group_id
    qualities = [
        q.model_copy(
            update={
                "exact_duplicate_group": dup_lookup.get(q.candidate_id, {}).get("exact"),
                "structural_duplicate_group": dup_lookup.get(q.candidate_id, {}).get("structural"),
                "semantic_duplicate_group": dup_lookup.get(q.candidate_id, {}).get("semantic"),
                "is_duplicate_representative": all(
                    group.representative_id == q.candidate_id
                    for group in duplicates.groups
                    if q.candidate_id in group.member_ids
                ),
            }
        )
        for q in qualities
    ]

    diversity, diversity_features = compute_diversity(
        qualities, sides["candidate_sql"], sides["schemas"]
    )
    coverage = compute_coverage(qualities, sides["candidate_sql"])
    difficulty, difficulty_features = analyze_difficulty(qualities, sides["candidate_sql"])
    qualities = [
        q.model_copy(
            update={
                "diversity_features": diversity_features[q.candidate_id],
                "difficulty_features": difficulty_features[q.candidate_id],
            }
        )
        for q in qualities
    ]

    contamination_flags, contamination = analyze_contamination(
        qualities, sides["canonical_tasks"], sides["candidate_sql"], config
    )
    qualities = [
        q.model_copy(update={"contamination_flags": contamination_flags[q.candidate_id]})
        for q in qualities
    ]

    audit_sample = sample_audit(qualities, config)
    audit_results: dict[str, str] = {}
    if audit_overrides:
        for candidate_id, result in sorted(audit_overrides.items()):
            status = _as_audit_status(result, candidate_id)
            audit_sample = record_audit_result(audit_sample, candidate_id, status)
            audit_results[candidate_id] = status
    audited_ids = {item.candidate_id for item in audit_sample.items}
    qualities = [
        q.model_copy(
            update={
                "audit_required": q.candidate_id in audited_ids,
                "audit_status": next(
                    (i.status for i in audit_sample.items if i.candidate_id == q.candidate_id),
                    None,
                ),
                "auditor_result": next(
                    (i.result for i in audit_sample.items if i.candidate_id == q.candidate_id),
                    None,
                ),
                "audit_reason": next(
                    (
                        ", ".join(i.reasons)
                        for i in audit_sample.items
                        if i.candidate_id == q.candidate_id
                    ),
                    "",
                ),
            }
        )
        for q in qualities
    ]

    qualities = select_golden(qualities, config, audit_results, justifications, quarantined)
    health = build_health_report(
        qualities, duplicates, diversity, coverage, difficulty, contamination, audit_sample, config
    )
    logger.info(
        "dataset analysis complete",
        extra={"golden": sum(1 for q in qualities if q.decision == "GOLDEN")},
    )
    return DatasetAnalysis(
        records=sorted(records, key=lambda r: r.candidate.candidate_id),
        qualities=qualities,
        duplicates=duplicates,
        diversity=diversity,
        coverage=coverage,
        difficulty=difficulty,
        contamination=contamination,
        audit_sample=audit_sample,
        health=health,
        config=config,
    )
