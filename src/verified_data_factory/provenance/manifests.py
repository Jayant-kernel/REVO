"""Reproduction manifests (Phase 6, §35).

A self-contained description of what reproducing a dataset snapshot
would require. It records identities and references — never claims to
contain data that is not actually present (each section notes its own
provenance).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .hashing import content_id
from .models import PROVENANCE_ENGINE_VERSION, PROVENANCE_SCHEMA_VERSION


class ReproductionManifest(BaseModel):
    """What reproduction requires (references, not a replay button)."""

    model_config = {"frozen": True}

    manifest_id: str = Field(min_length=1)
    dataset_snapshot_id: str = Field(min_length=1)
    factory_version: str = Field(min_length=1)
    provenance_version: str = Field(min_length=1)
    source_snapshot: dict[str, Any] = Field(default_factory=dict)
    dependency_snapshot: dict[str, Any] = Field(default_factory=dict)
    environment_snapshot: dict[str, Any] = Field(default_factory=dict)
    model_snapshots: list[dict[str, Any]] = Field(default_factory=list)
    configuration_snapshots: list[dict[str, Any]] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    verification_ids: list[str] = Field(default_factory=list)
    quality_ids: list[str] = Field(default_factory=list)
    golden_record_ids: list[str] = Field(default_factory=list)
    artifact_refs: list[dict[str, Any]] = Field(default_factory=list)
    reproducibility: dict[str, Any] = Field(default_factory=dict)
    replay_scope: Literal["comparison", "full"] = "comparison"
    replay_notes: str = Field(default="")
    schema_version: str = Field(min_length=1)


def build_reproduction_manifest(
    dataset_snapshot_id: str,
    factory_version: str,
    source_snapshot: dict[str, Any] | None,
    dependency_snapshot: dict[str, Any] | None,
    environment_snapshot: dict[str, Any] | None,
    model_snapshots: list[dict[str, Any]],
    configuration_snapshots: list[dict[str, Any]],
    task_ids: list[str],
    candidate_ids: list[str],
    verification_ids: list[str],
    quality_ids: list[str],
    golden_record_ids: list[str],
    artifact_refs: list[dict[str, Any]],
    reproducibility: dict[str, Any],
) -> ReproductionManifest:
    """Assemble a manifest; id covers the deterministic subset only."""
    identity = {
        "dataset_snapshot_id": dataset_snapshot_id,
        "factory_version": factory_version,
        "source_snapshot": source_snapshot or {},
        "dependency_snapshot": dependency_snapshot or {},
        "model_snapshots": model_snapshots,
        "configuration_snapshots": configuration_snapshots,
        "task_ids": sorted(task_ids),
        "candidate_ids": sorted(candidate_ids),
        "verification_ids": sorted(verification_ids),
        "quality_ids": sorted(quality_ids),
        "golden_record_ids": sorted(golden_record_ids),
        "artifact_refs": artifact_refs,
    }
    return ReproductionManifest(
        manifest_id=content_id("REPRODUCTION_MANIFEST", PROVENANCE_SCHEMA_VERSION, identity),
        dataset_snapshot_id=dataset_snapshot_id,
        factory_version=factory_version,
        provenance_version=PROVENANCE_ENGINE_VERSION,
        source_snapshot=source_snapshot or {},
        dependency_snapshot=dependency_snapshot or {},
        environment_snapshot=environment_snapshot or {},
        model_snapshots=model_snapshots,
        configuration_snapshots=configuration_snapshots,
        task_ids=sorted(task_ids),
        candidate_ids=sorted(candidate_ids),
        verification_ids=sorted(verification_ids),
        quality_ids=sorted(quality_ids),
        golden_record_ids=sorted(golden_record_ids),
        artifact_refs=artifact_refs,
        reproducibility=reproducibility,
        replay_scope="comparison",
        replay_notes=(
            "MVP scope is comparison and evidence, not automated factory "
            "replay; re-running needs the pinned stack plus model access."
        ),
        schema_version=PROVENANCE_SCHEMA_VERSION,
    )
