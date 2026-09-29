"""Data product models (Phase 7).

Authority boundaries: Phase 4 owns correctness, Phase 5 owns Golden
qualification, Phase 6 owns provenance. These models own packaging,
release identity, schema versioning, and product validation — nothing
else. Every persisted product structure carries ``schema_version``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

PRODUCT_ENGINE_VERSION = "1.0"
PRODUCT_SCHEMA_VERSION = "1.0"
SQL_SCHEMA_NAME = "verified-data-factory/sql"
SQL_SCHEMA_VERSION = "1.0"
SQL_DIALECT = "DuckDB"
TRANSFORMATION_VERSION = "1.0"

ProductType = Literal["TRAIN", "PUBLIC_EVAL", "PRIVATE_EVAL", "BENCHMARK", "SAMPLE"]
Visibility = Literal["PUBLIC", "INTERNAL", "RESTRICTED"]
PackagingFormat = Literal["jsonl", "parquet"]
FieldClass = Literal["MODEL_INPUT", "MODEL_TARGET", "METADATA", "PROVENANCE", "INTERNAL_ONLY"]
SplitName = Literal["train", "public_eval", "private_eval", "benchmark"]
ValidationStatus = Literal["VALID", "INVALID"]


class FieldExposure(BaseModel):
    """One GoldenRecord field mapped to its exposure class."""

    model_config = {"frozen": True}

    field: str = Field(min_length=1)
    exposure: FieldClass
    product_field: str | None = None


class ProductSchema(BaseModel):
    """Versioned canonical product schema (never silently extended)."""

    model_config = {"frozen": True}

    schema_name: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    dialect: str = Field(min_length=1)
    fields: list[FieldExposure] = Field(min_length=1)
    transformation_version: str = Field(min_length=1)


class SplitPolicy(BaseModel):
    """Versioned deterministic split policy (group-aware, seeded)."""

    model_config = {"frozen": True}

    seed: int = 42
    train: float = Field(default=0.8, ge=0.0, le=1.0)
    public_eval: float = Field(default=0.1, ge=0.0, le=1.0)
    private_eval: float = Field(default=0.1, ge=0.0, le=1.0)
    group_by: Literal["semantic_group", "exact_group", "template", "none"] = "semantic_group"
    require_group_isolation: bool = True
    balance_families: bool = False
    min_split_size: int = Field(default=0, ge=0)
    policy_version: str = Field(default="1.0", min_length=1)


class ProductConfig(BaseModel):
    """Everything that defines one product build (content-addressed)."""

    model_config = {"frozen": True}

    product_name: str = Field(min_length=1)
    product_type: ProductType
    visibility: Visibility = "INTERNAL"
    schema_version: str = Field(default=SQL_SCHEMA_VERSION, min_length=1)
    output_format: PackagingFormat = "jsonl"
    include_sql_target: bool = True
    metadata_exposure: Literal["minimal", "standard", "full"] = "standard"
    provenance_exposure: bool = True
    split_policy: SplitPolicy = Field(default_factory=SplitPolicy)
    shard_size: int = Field(default=0, ge=0)
    preview_size: int = Field(default=5, ge=0)
    output_dir: str = Field(default="release")
    config_version: str = Field(default="1.0", min_length=1)


class TrainingRecord(BaseModel):
    """Canonical training payload: model input + target, provenance by reference."""

    model_config = {"frozen": True, "populate_by_name": True}

    task_id: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    schema_: str = Field(alias="schema", min_length=1)
    sql: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    template_version: int = Field(ge=1)
    task_family: str = Field(min_length=1)
    difficulty: int = Field(ge=1, le=5)
    dialect: str = Field(default=SQL_DIALECT, min_length=1)
    golden_record_id: str = Field(min_length=1)
    dataset_snapshot_id: str = Field(min_length=1)


class EvaluationRecord(BaseModel):
    """Evaluation payload: target exposure governed by product profile."""

    model_config = {"frozen": True, "populate_by_name": True}

    task_id: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    schema_: str = Field(alias="schema", min_length=1)
    sql: str | None = None
    template_id: str = Field(min_length=1)
    template_version: int = Field(ge=1)
    task_family: str = Field(min_length=1)
    difficulty: int = Field(ge=1, le=5)
    dialect: str = Field(default=SQL_DIALECT, min_length=1)
    golden_record_id: str = Field(min_length=1)
    dataset_snapshot_id: str = Field(min_length=1)
    split: SplitName = "public_eval"


class BenchmarkRecord(EvaluationRecord):
    """Benchmark payload: stable benchmark item with explicit item id."""

    benchmark_item_id: str = Field(min_length=1)


class DatasetSplit(BaseModel):
    """One named split: deterministic ordered membership."""

    model_config = {"frozen": True}

    name: SplitName
    candidate_ids: list[str] = Field(default_factory=list)
    record_count: int = Field(ge=0)


class ShardManifest(BaseModel):
    model_config = {"frozen": True}

    shard_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    record_count: int = Field(ge=0)
    byte_size: int = Field(ge=0)
    content_hash: str = Field(min_length=1)


class ReleaseFile(BaseModel):
    model_config = {"frozen": True}

    relative_path: str = Field(min_length=1)
    byte_size: int = Field(ge=0)
    content_hash: str = Field(min_length=1)
    media_type: str = Field(min_length=1)


class ReleaseManifest(BaseModel):
    """Authoritative release descriptor (content identity excludes timestamps).

    ``split_counts`` is the full deterministic split plan (all four
    splits); ``record_count`` is what this release actually ships (the
    product-type split only).
    """

    model_config = {"frozen": True}

    product_name: str = Field(min_length=1)
    product_type: ProductType
    visibility: Visibility
    release_id: str = Field(min_length=1)
    dataset_snapshot_id: str = Field(min_length=1)
    schema_name: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    product_config_id: str = Field(min_length=1)
    split_policy_id: str = Field(min_length=1)
    transformation_version: str = Field(min_length=1)
    output_format: PackagingFormat = "jsonl"
    record_count: int = Field(ge=0)
    split_counts: dict[str, int] = Field(default_factory=dict)
    shard_count: int = Field(ge=0)
    shards: list[ShardManifest] = Field(default_factory=list)
    files: list[ReleaseFile] = Field(default_factory=list)
    created_at: str = ""
    factory_version: str = Field(min_length=1)
    provenance_version: str = Field(min_length=1)
    manifest_schema_version: str = Field(min_length=1)


class ValidationCheck(BaseModel):
    model_config = {"frozen": True}

    check: str = Field(min_length=1)
    passed: bool
    detail: str = ""


class ReleaseValidationReport(BaseModel):
    """Structured validation outcome: errors fail, warnings inform."""

    model_config = {"frozen": True}

    status: ValidationStatus = "INVALID"
    errors: list[ValidationCheck] = Field(default_factory=list)
    warnings: list[ValidationCheck] = Field(default_factory=list)
    record_count: int = Field(ge=0, default=0)
    file_count: int = Field(ge=0, default=0)
    checksum_status: str = ""
    schema_status: str = ""
    split_status: str = ""
    provenance_status: str = ""
    manifest_status: str = ""
    schema_version: str = Field(min_length=1)


class ReleaseDiff(BaseModel):
    model_config = {"frozen": True}

    release_a: str = Field(min_length=1)
    release_b: str = Field(min_length=1)
    records_added: list[str] = Field(default_factory=list)
    records_removed: list[str] = Field(default_factory=list)
    records_changed: list[str] = Field(default_factory=list)
    splits_changed: bool = False
    schema_changed: bool = False
    config_changed: bool = False
    snapshot_changed: bool = False
    format_changed: bool = False
    schema_version: str = Field(min_length=1)


class ProductMetrics(BaseModel):
    """Release-level metrics referenced (not recomputed) from Phase 5."""

    model_config = {"frozen": True}

    record_count: int = Field(ge=0, default=0)
    train_count: int = Field(ge=0, default=0)
    public_eval_count: int = Field(ge=0, default=0)
    private_eval_count: int = Field(ge=0, default=0)
    benchmark_count: int = Field(ge=0, default=0)
    family_distribution: dict[str, int] = Field(default_factory=dict)
    difficulty_distribution: dict[str, int] = Field(default_factory=dict)
    coverage_summary: dict[str, Any] = Field(default_factory=dict)
    duplicate_summary: dict[str, Any] = Field(default_factory=dict)
    verification_summary: dict[str, Any] = Field(default_factory=dict)
    audit_summary: dict[str, Any] = Field(default_factory=dict)
    contamination_summary: dict[str, Any] = Field(default_factory=dict)


class RowManifest(BaseModel):
    """Per-record provenance pointer for samples and releases (audit layer).

    Sourced from the provenance graph and release pipeline — never
    hand-assembled. Fields unavailable for a record stay None rather
    than invented.
    """

    model_config = {"frozen": True}

    record_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    template_version: int = Field(ge=1)
    model_name: str = Field(min_length=1)
    model_revision: str = Field(default="UNKNOWN")
    prompt_version: str = ""
    generation_run_id: str | None = None
    candidate_id: str = Field(min_length=1)
    execution_run_id: str | None = None
    verification_run_id: str | None = None
    quality_run_id: str | None = None
    golden_selection: str | None = None
    dataset_snapshot_id: str = Field(min_length=1)
    release_id: str | None = None
    schema_version: str = Field(min_length=1)


# Customer-visible row-manifest keys. Everything else stays internal.
ROW_MANIFEST_PUBLIC_KEYS: tuple[str, ...] = (
    "record_id",
    "task_id",
    "family",
    "template_id",
    "template_version",
    "model_name",
    "model_revision",
    "prompt_version",
    "candidate_id",
    "dataset_snapshot_id",
    "release_id",
)


class DiversityReport(BaseModel):
    """Deterministic dataset-level diversity evidence (no scores, no ranks)."""

    model_config = {"frozen": True}

    record_count: int = Field(ge=0, default=0)
    instruction_unique_normalized: int = Field(ge=0, default=0)
    instruction_unique_ratio: float | None = None
    instruction_top_share: float | None = None
    instruction_top5_share: float | None = None
    instruction_top_samples: list[dict[str, Any]] = Field(default_factory=list)
    task_unique_count: int = Field(ge=0, default=0)
    template_counts: dict[str, int] = Field(default_factory=dict)
    semantic_groups: int = Field(ge=0, default=0)
    semantic_largest_group: int = Field(ge=0, default=0)
    exact_groups: int = Field(ge=0, default=0)
    sql_features: dict[str, dict[str, Any]] = Field(default_factory=dict)
    sql_family_features: dict[str, dict[str, int]] = Field(default_factory=dict)
    sql_unique_normalized: int = Field(ge=0, default=0)
    sql_unique_ratio: float | None = None
    schema_identities: int = Field(ge=0, default=0)
    schema_table_histogram: dict[str, int] = Field(default_factory=dict)
    edge_counts: dict[str, int] = Field(default_factory=dict)
    schema_version: str = Field(min_length=1)


class CensusReport(BaseModel):
    """Reproducible corpus census: record-level evidence, aggregated deterministically."""

    model_config = {"frozen": True}

    record_count: int = Field(ge=0, default=0)
    strength_distribution: dict[str, int] = Field(default_factory=dict)
    mutation_score_distribution: dict[str, int] = Field(default_factory=dict)
    mutation_applicable_histogram: dict[str, int] = Field(default_factory=dict)
    zero_applicable_count: int = Field(ge=0, default=0)
    zero_applicable_ids: list[str] = Field(default_factory=list)
    unjustified_zero_applicable_count: int = Field(ge=0, default=0)
    family_counts: dict[str, int] = Field(default_factory=dict)
    generation_run_counts: dict[str, int] = Field(default_factory=dict)
    model_revision_counts: dict[str, int] = Field(default_factory=dict)
    template_version_counts: dict[str, int] = Field(default_factory=dict)
    prompt_version_counts: dict[str, int] = Field(default_factory=dict)
    contamination_by_type: dict[str, int] = Field(default_factory=dict)
    contamination_hard_count: int = Field(ge=0, default=0)
    quarantine_count: int = Field(ge=0, default=0)
    quarantined_ids: list[str] = Field(default_factory=list)
    governance_unresolved_count: int = Field(ge=0, default=0)
    provenance_complete_count: int = Field(ge=0, default=0)
    provenance_missing_fields: dict[str, int] = Field(default_factory=dict)
    duplicate_exact_groups: int = Field(ge=0, default=0)
    duplicate_semantic_groups: int = Field(ge=0, default=0)
    population_duplicate_rates: dict[str, float] = Field(default_factory=dict)
    diversity: DiversityReport | None = None
    all_strong: bool = False
    all_scored_at_threshold: bool = False
    schema_version: str = Field(min_length=1)


class AuditReport(BaseModel):
    """Machine-generated audit report with factual readiness statuses (no scores)."""

    model_config = {"frozen": True}

    corpus: dict[str, Any] = Field(default_factory=dict)
    verification: dict[str, Any] = Field(default_factory=dict)
    governance: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    diversity: dict[str, Any] = Field(default_factory=dict)
    quarantine: dict[str, Any] = Field(default_factory=dict)
    readiness: dict[str, str] = Field(default_factory=dict)
    schema_version: str = Field(min_length=1)


class NoveltyReport(BaseModel):
    """Cross-run novelty of new Golden records against an existing pool.

    Evidence metrics only: no rejection decisions, no scores. A record
    counts as novel when neither its normalized SQL, semantic group,
    structural signature, task, schema, nor edge combination appears in
    the pool.
    """

    model_config = {"frozen": True}

    new_total: int = Field(ge=0, default=0)
    pool_total: int = Field(ge=0, default=0)
    exact_duplicates: int = Field(ge=0, default=0)
    semantic_duplicates: int = Field(ge=0, default=0)
    structural_near_duplicates: int = Field(ge=0, default=0)
    novel_golden: int = Field(ge=0, default=0)
    novel_tasks: int = Field(ge=0, default=0)
    novel_sql_structures: int = Field(ge=0, default=0)
    novel_schemas: int = Field(ge=0, default=0)
    novel_edge_combinations: int = Field(ge=0, default=0)
    novel_ids: list[str] = Field(default_factory=list)
    schema_version: str = Field(min_length=1)


class MetricValue(BaseModel):
    """One measured metric with its explicit cost basis."""

    model_config = {"frozen": True}

    value: float | None = None
    basis: Literal["OBSERVED", "ASSUMED", "PROJECTED", "UNKNOWN"] = "UNKNOWN"
    unit: str = ""
    note: str = ""


class RunEconomics(BaseModel):
    """Run-level economics in native units; money only with a price table."""

    model_config = {"frozen": True}

    generation_wall_s: MetricValue = Field(default_factory=MetricValue)
    generation_candidates: MetricValue = Field(default_factory=MetricValue)
    prompt_tokens: MetricValue = Field(default_factory=MetricValue)
    completion_tokens: MetricValue = Field(default_factory=MetricValue)
    model_calls: MetricValue = Field(default_factory=MetricValue)
    executions: MetricValue = Field(default_factory=MetricValue)
    verifications: MetricValue = Field(default_factory=MetricValue)
    mutation_runs: MetricValue = Field(default_factory=MetricValue)
    verification_wall_s: MetricValue = Field(default_factory=MetricValue)
    artifact_bytes: MetricValue = Field(default_factory=MetricValue)
    dataset_bytes: MetricValue = Field(default_factory=MetricValue)
    machine_identity: str = ""
    cpu_identity: str = "UNKNOWN"
    gpu_identity: str = "UNKNOWN"
    power_watts: MetricValue = Field(default_factory=MetricValue)
    per_candidate_s: MetricValue = Field(default_factory=MetricValue)
    per_pass_s: MetricValue = Field(default_factory=MetricValue)
    per_golden_s: MetricValue = Field(default_factory=MetricValue)
    per_novel_golden_s: MetricValue = Field(default_factory=MetricValue)
    projected_s_for_1000_golden: MetricValue = Field(default_factory=MetricValue)
    projected_s_for_10000_golden: MetricValue = Field(default_factory=MetricValue)
    monetary: dict[str, MetricValue] = Field(default_factory=dict)
    schema_version: str = Field(min_length=1)
