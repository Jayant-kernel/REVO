"""Provenance object model (Phase 6, §5–§7).

Every persisted provenance structure carries ``schema_version``. Content
identities (``sha256:<hex>``) cover identity-bearing payloads only —
operational fields (run ids, timestamps) live outside hashed envelopes
and are documented as such per model.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

PROVENANCE_ENGINE_VERSION = "1.0"
PROVENANCE_SCHEMA_VERSION = "1.0"

NodeType = Literal[
    "TASK_TEMPLATE",
    "TASK_INSTANCE",
    "GENERATION_RUN",
    "CANDIDATE_SOLUTION",
    "EXECUTION_RUN",
    "EXECUTION_RESULT",
    "VERIFICATION_RUN",
    "VERIFICATION_RESULT",
    "QUALITY_RUN",
    "RECORD_QUALITY",
    "AUDIT_SAMPLE",
    "AUDIT_RESULT",
    "GOLDEN_SELECTION",
    "GOLDEN_RECORD",
    "DATASET_SNAPSHOT",
    "CONFIGURATION",
    "SOURCE_SNAPSHOT",
    "ENVIRONMENT_SNAPSHOT",
    "MODEL_SNAPSHOT",
    "ARTIFACT",
]

EdgeType = Literal[
    "DERIVED_FROM",
    "GENERATED_BY",
    "EXECUTED_BY",
    "VERIFIED_BY",
    "QUALIFIED_BY",
    "AUDITED_BY",
    "SELECTED_BY",
    "INCLUDED_IN",
    "EXPORTED_AS",
    "USES_CONFIGURATION",
    "USES_ENVIRONMENT",
    "USES_MODEL",
    "USES_ARTIFACT",
    "SUPERSEDES",
]

ReproStatus = Literal["VERIFIED", "CONDITIONAL", "NOT_VERIFIED", "NON_REPLAYABLE", "UNKNOWN"]

CompletenessCode = Literal[
    "MISSING_TASK",
    "MISSING_CANDIDATE",
    "MISSING_EXECUTION",
    "MISSING_VERIFICATION",
    "MISSING_QUALITY",
    "MISSING_SELECTION",
    "MISSING_ARTIFACT",
    "MISSING_CONFIGURATION",
    "MISSING_ENVIRONMENT",
]

ActivityType = Literal[
    "GENERATION_RUN",
    "EXECUTION_RUN",
    "VERIFICATION_RUN",
    "QUALITY_RUN",
    "GOLDEN_SELECTION_RUN",
    "EXPORT_RUN",
    "PROVENANCE_RUN",
]

ActivityStatus = Literal["SUCCEEDED", "FAILED", "INCONCLUSIVE"]


class ProvenanceNode(BaseModel):
    """An entity that exists. Identity covers payload only (no timestamps)."""

    model_config = {"frozen": True}

    node_id: str = Field(min_length=1)
    node_type: NodeType
    schema_version: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class ProvenanceEdge(BaseModel):
    """A lineage relationship. ID is deterministic over (source, rel, target)."""

    model_config = {"frozen": True}

    edge_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    relationship: EdgeType
    schema_version: str = Field(min_length=1)


class ProvenanceActivity(BaseModel):
    """Something that produced or transformed entities (operational record)."""

    model_config = {"frozen": True}

    run_id: str = Field(min_length=1)
    activity_type: ActivityType
    tool_version: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    configuration_id: str | None = None
    source_snapshot_id: str | None = None
    environment_snapshot_id: str | None = None
    status: ActivityStatus = "SUCCEEDED"
    started_at: str = ""
    finished_at: str = ""


class ArtifactRef(BaseModel):
    """Reference to (not a copy of) an artifact, content-addressed."""

    model_config = {"frozen": True}

    artifact_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    media_type: str = Field(min_length=1)
    logical_name: str = Field(min_length=1)
    relative_locator: str = Field(min_length=1)
    created_by_run: str | None = None
    compression: str | None = None
    encoding: str | None = None
    schema_version: str = Field(min_length=1)


class ConfigSnapshot(BaseModel):
    """Immutable, content-addressed configuration (never a bare path)."""

    model_config = {"frozen": True}

    configuration_id: str = Field(min_length=1)
    config_name: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    content: dict[str, Any] = Field(default_factory=dict)


class SourceSnapshot(BaseModel):
    """Repository state. Dirty trees are recorded, never hidden."""

    model_config = {"frozen": True}

    source_snapshot_id: str = Field(min_length=1)
    repository: str = Field(default="")
    git_commit: str = Field(default="UNKNOWN")
    git_branch: str = Field(default="UNKNOWN")
    working_tree_clean: bool = False
    source_fingerprint: str = Field(default="UNKNOWN")
    schema_version: str = Field(min_length=1)


class EnvironmentSnapshot(BaseModel):
    """Safe runtime metadata. Secrets are never captured (§10)."""

    model_config = {"frozen": True}

    environment_snapshot_id: str = Field(min_length=1)
    python_version: str = Field(default="UNKNOWN")
    platform: str = Field(default="UNKNOWN")
    architecture: str = Field(default="UNKNOWN")
    operating_system: str = Field(default="UNKNOWN")
    docker_client_version: str | None = None
    docker_server_version: str | None = None
    duckdb_version: str | None = None
    dependency_lock_hash: str = Field(default="UNKNOWN")
    container_image: str | None = None
    container_image_digest: str | None = None
    image_digest_status: Literal["PINNED", "RECORDED", "UNAVAILABLE"] = "UNAVAILABLE"
    container_python_version: str | None = None
    container_duckdb_version: str | None = None
    schema_version: str = Field(min_length=1)


class ModelSnapshot(BaseModel):
    """Model origin metadata. No commercial-rights inference attached."""

    model_config = {"frozen": True}

    model_snapshot_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    model_revision: str = Field(default="UNKNOWN")
    model_family: str | None = None
    license_identifier: str | None = None
    source_registry: str | None = None
    endpoint_identifier_hash: str | None = None
    generation_config: dict[str, Any] = Field(default_factory=dict)
    prompt_version: str | None = None
    generation_schema_version: str | None = None
    deterministic_replay: bool = False
    schema_version: str = Field(min_length=1)


class RunManifest(BaseModel):
    """Auditable record of one provenance run.

    ``manifest_id`` covers the deterministic subset only (application,
    source, dependencies); operational fields (run id, timestamps) are
    recorded but excluded from the identity.
    """

    model_config = {"frozen": True}

    manifest_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    factory_version: str = Field(min_length=1)
    provenance_engine_version: str = Field(min_length=1)
    phase: str = Field(default="provenance")
    schema_versions: dict[str, str] = Field(default_factory=dict)
    source_snapshot_id: str = Field(default="UNKNOWN")
    dependency_lock_hash: str = Field(default="UNKNOWN")
    environment_snapshot_id: str | None = None
    started_at: str = ""
    finished_at: str = ""
    schema_version: str = Field(min_length=1)


class DatasetSnapshot(BaseModel):
    """Immutable, content-defined Golden membership.

    Identity covers the ordered canonical Golden record content IDs plus
    selection metadata — never timestamps, locations, or display names.
    """

    model_config = {"frozen": True}

    dataset_snapshot_id: str = Field(min_length=1)
    dataset_name: str = Field(min_length=1)
    dataset_schema_version: str = Field(min_length=1)
    golden_record_ids: list[str] = Field(default_factory=list)
    record_count: int = Field(ge=0)
    selection_config_id: str = Field(min_length=1)
    quality_engine_version: str = Field(min_length=1)
    provenance_engine_version: str = Field(min_length=1)
    created_at: str = ""
    schema_version: str = Field(min_length=1)


class LayerAssessment(BaseModel):
    """One reproducibility layer: status plus supporting reasons."""

    model_config = {"frozen": True}

    status: ReproStatus = "UNKNOWN"
    reasons: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class ReproducibilityReport(BaseModel):
    """Per-layer evidence plus an overall status (never a lone boolean)."""

    model_config = {"frozen": True}

    task_reproducibility: LayerAssessment = Field(default_factory=LayerAssessment)
    generation_reproducibility: LayerAssessment = Field(default_factory=LayerAssessment)
    execution_reproducibility: LayerAssessment = Field(default_factory=LayerAssessment)
    verification_reproducibility: LayerAssessment = Field(default_factory=LayerAssessment)
    quality_reproducibility: LayerAssessment = Field(default_factory=LayerAssessment)
    dataset_reproducibility: LayerAssessment = Field(default_factory=LayerAssessment)
    overall_status: ReproStatus = "UNKNOWN"
    reasons: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    schema_version: str = Field(min_length=1)


class CompletenessIssue(BaseModel):
    model_config = {"frozen": True}

    code: CompletenessCode
    detail: str = ""


class ProvenanceCompletenessReport(BaseModel):
    model_config = {"frozen": True}

    complete: bool
    errors: list[CompletenessIssue] = Field(default_factory=list)
    checked_records: int = Field(ge=0, default=0)
    schema_version: str = Field(min_length=1)


class ReproducibilityDifference(BaseModel):
    model_config = {"frozen": True}

    category: str = Field(min_length=1)
    expected: str = ""
    actual: str = ""


class ReproducibilityDiff(BaseModel):
    model_config = {"frozen": True}

    status: ReproStatus = "UNKNOWN"
    differences: list[ReproducibilityDifference] = Field(default_factory=list)
    schema_version: str = Field(min_length=1)


class ProvenanceConfig(BaseModel):
    """Provenance layer settings (versioned like every other config)."""

    model_config = {"frozen": True}

    emit_raw_artifacts: bool = True
    max_inline_bytes: int = Field(default=1 << 20, ge=1024)
    source_scope: list[str] = Field(
        default_factory=lambda: ["src/verified_data_factory", "pyproject.toml", "configs/"]
    )
    config_version: str = Field(default="1.0", min_length=1)
