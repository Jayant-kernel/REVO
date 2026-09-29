"""Quality data models (Phase 5).

Central distinction: Phase 4 verdicts say whether a candidate is correct;
Phase 5 evidence says whether a verified record belongs in the Golden
Dataset. A PASS is necessary but never sufficient — every exclusion keeps
its reasons, and the underlying evidence is never overwritten.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.sandbox.models import ExecutionResult
from verified_data_factory.task_engine.models import TaskInstance
from verified_data_factory.verification.models import VerificationResult

QUALITY_ENGINE_VERSION = "1.0"
QUALITY_CONFIG_VERSION = "1.0"

DatasetRole = Literal["TRAIN", "PUBLIC_EVAL", "PRIVATE_EVAL", "UNKNOWN"]
GoldenDecision = Literal["GOLDEN", "EXCLUDED", "INCONCLUSIVE", "AUDIT_REQUIRED"]
AuditStatus = Literal["PENDING", "PASS", "FAIL", "UNCLEAR"]
RiskBand = Literal["HIGH", "MEDIUM", "LOW"]
DifficultyMethod = Literal["DECLARED", "EMPIRICAL"]
DuplicateType = Literal["EXACT", "STRUCTURAL", "SEMANTIC"]


class VerifiedRecord(BaseModel):
    """One Phase 4 output bundle: the unit Phase 5 reasons about."""

    model_config = {"frozen": True}

    task: TaskInstance
    candidate: CandidateSolution
    execution: ExecutionResult
    verification: VerificationResult
    role: DatasetRole = "UNKNOWN"


class TaskQualityEvidence(BaseModel):
    model_config = {"frozen": True}

    valid: bool
    validation_errors: list[str] = Field(default_factory=list)
    semantic_required: list[str] = Field(default_factory=list)
    semantic_present: list[str] = Field(default_factory=list)
    semantic_completeness_rate: float = Field(default=0.0, ge=0, le=1)
    ambiguity_flags: list[str] = Field(default_factory=list)
    edge_cases_expected: list[str] = Field(default_factory=list)
    edge_cases_present: list[str] = Field(default_factory=list)
    edge_case_coverage_rate: float = Field(default=0.0, ge=0, le=1)
    schema_consistent: bool = False
    schema_issues: list[str] = Field(default_factory=list)
    instruction_spec_consistent: bool = False
    instruction_issues: list[str] = Field(default_factory=list)


class VerificationSummary(BaseModel):
    """Phase 4 evidence restated (never recomputed) for qualification."""

    model_config = {"frozen": True}

    verdict: str
    verification_strength: str
    failure_code: str | None = None
    original_execution_pass: bool = False
    hidden_tests_pass: bool = False
    hidden_failed: int = 0
    property_tests_pass: bool = False
    metamorphic_tests_pass: bool = False
    mutation_score: float | None = None
    mutation_applicable: int = 0
    mutation_status: Literal["SCORED", "NOT_APPLICABLE"] = "NOT_APPLICABLE"


class DuplicateGroup(BaseModel):
    model_config = {"frozen": True}

    group_id: str = Field(min_length=1)
    duplicate_type: DuplicateType
    member_ids: list[str] = Field(min_length=1)
    representative_id: str = Field(min_length=1)


class DuplicateReport(BaseModel):
    model_config = {"frozen": True}

    groups: list[DuplicateGroup] = Field(default_factory=list)


class ContaminationFlag(BaseModel):
    model_config = {"frozen": True}

    flag_type: str = Field(min_length=1)
    detail: str = ""
    hard: bool = False


class AuditItem(BaseModel):
    model_config = {"frozen": True}

    audit_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    risk_score: int = Field(ge=0, default=0)
    risk_band: RiskBand = "LOW"
    reasons: list[str] = Field(default_factory=list)
    status: AuditStatus = "PENDING"
    result: AuditStatus | None = None
    note: str = ""


class AuditSample(BaseModel):
    model_config = {"frozen": True}

    items: list[AuditItem] = Field(default_factory=list)
    selection_seed: int = 0
    sampled_count: int = Field(ge=0, default=0)


class RecordQuality(BaseModel):
    """Full per-record quality evidence plus the final decision."""

    model_config = {"frozen": True, "populate_by_name": True}

    candidate_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    template_version: int = Field(ge=1)
    family: str = Field(min_length=1)
    seed: int = Field(ge=0)
    difficulty: int = Field(ge=1, le=5, default=1)
    role: DatasetRole = "UNKNOWN"
    task_quality: TaskQualityEvidence
    verification: VerificationSummary
    exact_duplicate_group: str | None = None
    structural_duplicate_group: str | None = None
    semantic_duplicate_group: str | None = None
    is_duplicate_representative: bool = True
    diversity_features: dict[str, Any] = Field(default_factory=dict)
    difficulty_features: dict[str, Any] = Field(default_factory=dict)
    contamination_flags: list[ContaminationFlag] = Field(default_factory=list)
    audit_required: bool = False
    audit_status: AuditStatus | None = None
    auditor_result: AuditStatus | None = None
    audit_reason: str = ""
    decision: GoldenDecision = "INCONCLUSIVE"
    decision_reasons: list[str] = Field(default_factory=list)
    mutation_justification: str = ""


class FamilyDistribution(BaseModel):
    model_config = {"frozen": True}

    counts: dict[str, int] = Field(default_factory=dict)
    percentages: dict[str, float] = Field(default_factory=dict)
    entropy: float = Field(ge=0, default=0.0)


class DiversityReport(BaseModel):
    model_config = {"frozen": True}

    family: FamilyDistribution = Field(default_factory=FamilyDistribution)
    sql_constructs: dict[str, int] = Field(default_factory=dict)
    schema_fingerprints: dict[str, int] = Field(default_factory=dict)
    edge_cases: dict[str, int] = Field(default_factory=dict)
    operator_categories: dict[str, int] = Field(default_factory=dict)


class CoverageReport(BaseModel):
    model_config = {"frozen": True}

    families_covered: list[str] = Field(default_factory=list)
    families_total: int = 0
    family_coverage_rate: float = Field(default=0.0, ge=0, le=1)
    constructs_covered: list[str] = Field(default_factory=list)
    constructs_total: int = 0
    construct_coverage_rate: float = Field(default=0.0, ge=0, le=1)
    edge_cases_covered: list[str] = Field(default_factory=list)
    edge_cases_total: int = 0
    edge_case_coverage_rate: float = Field(default=0.0, ge=0, le=1)
    uncovered_families: list[str] = Field(default_factory=list)
    uncovered_constructs: list[str] = Field(default_factory=list)
    uncovered_edge_cases: list[str] = Field(default_factory=list)


class DifficultyReport(BaseModel):
    model_config = {"frozen": True}

    method: DifficultyMethod = "DECLARED"
    declared_distribution: dict[str, int] = Field(default_factory=dict)
    empirical_available: bool = False
    empirical_reason: str = "single attempt per record; no solve-rate data"
    complexity_features: dict[str, float] = Field(default_factory=dict)


class ContaminationReport(BaseModel):
    model_config = {"frozen": True}

    flagged_count: int = Field(ge=0, default=0)
    contaminated_rate: float = Field(default=0.0, ge=0, le=1)
    split_overlap_count: int = Field(ge=0, default=0)
    flags_by_type: dict[str, int] = Field(default_factory=dict)


class FailureBreakdown(BaseModel):
    model_config = {"frozen": True}

    candidates: int = 0
    verified_pass: int = 0
    golden: int = 0
    excluded: int = 0
    inconclusive: int = 0
    audit_required: int = 0
    by_reason: dict[str, int] = Field(default_factory=dict)


class DatasetHealthReport(BaseModel):
    """Authoritative multi-dimensional health (no single magic score)."""

    model_config = {"frozen": True, "populate_by_name": True}

    quality_engine_version: str = Field(min_length=1)
    quality_config_version: str = Field(min_length=1)
    selection_seed: int = 0
    production: dict[str, float] = Field(default_factory=dict)
    correctness: dict[str, float] = Field(default_factory=dict)
    task_health: dict[str, float] = Field(default_factory=dict)
    duplicates: dict[str, float] = Field(default_factory=dict)
    diversity: DiversityReport = Field(default_factory=DiversityReport)
    coverage: CoverageReport = Field(default_factory=CoverageReport)
    difficulty: DifficultyReport = Field(default_factory=DifficultyReport)
    reliability: dict[str, float] = Field(default_factory=dict)
    contamination: ContaminationReport = Field(default_factory=ContaminationReport)
    golden: dict[str, float] = Field(default_factory=dict)
    golden_family_distribution: dict[str, float] = Field(default_factory=dict)
    golden_difficulty_distribution: dict[str, float] = Field(default_factory=dict)
    golden_coverage_families: float = 0.0
    failures: FailureBreakdown = Field(default_factory=FailureBreakdown)


class GoldenRecord(BaseModel):
    """Canonical Golden export shape (per docs/golden-record.md).

    ``schema`` serializes under its contract name via alias (internal
    attribute ``schema_`` avoids shadowing ``BaseModel.schema``).
    """

    model_config = {"frozen": True, "populate_by_name": True}

    record_id: str = Field(min_length=1)
    record_schema_version: str = Field(default="2.0", min_length=1)
    candidate_id: str = Field(min_length=1)
    task: dict[str, Any]
    instruction: str
    schema_: list[dict[str, Any]] = Field(alias="schema")
    fixture: dict[str, Any]
    candidate_solution: str
    verification: dict[str, Any]
    quality: dict[str, Any]
    dataset_role: DatasetRole = "UNKNOWN"
    audit_status: AuditStatus | None = None

    @model_validator(mode="before")
    @classmethod
    def derive_legacy_record_id(cls, value: Any) -> Any:
        """Keep pre-v2 Golden artifacts readable while assigning content identity."""
        if not isinstance(value, dict) or value.get("record_id"):
            return value
        upgraded = dict(value)
        schema_version = str(upgraded.get("record_schema_version", "2.0"))
        payload = {
            "record_schema_version": schema_version,
            "task": upgraded.get("task", {}),
            "instruction": upgraded.get("instruction", ""),
            "schema": upgraded.get("schema", upgraded.get("schema_", [])),
            "candidate_solution": upgraded.get("candidate_solution", ""),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        upgraded["record_id"] = f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"
        upgraded["record_schema_version"] = schema_version
        return upgraded
