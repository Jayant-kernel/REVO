"""Reproducibility assessment (Phase 6, §26–§29).

Levels are evaluated independently from recorded evidence — never by
re-running the factory. Severity order (best to worst):
VERIFIED < CONDITIONAL < NOT_VERIFIED < NON_REPLAYABLE < UNKNOWN.
Model generation is honestly CONDITIONAL at best: the origin is
reconstructable from preserved artifacts, but bit-for-bit regeneration
is not guaranteed unless the stack says so.
"""

from __future__ import annotations

from typing import Any

from .models import (
    PROVENANCE_SCHEMA_VERSION,
    LayerAssessment,
    ReproducibilityDiff,
    ReproducibilityDifference,
    ReproducibilityReport,
    ReproStatus,
)

_SEVERITY: dict[ReproStatus, int] = {
    "VERIFIED": 0,
    "CONDITIONAL": 1,
    "NOT_VERIFIED": 2,
    "NON_REPLAYABLE": 3,
    "UNKNOWN": 4,
}


def worst_status(statuses: list[ReproStatus]) -> ReproStatus:
    """Overall status is the worst layer status (explicit, documented)."""
    return max(statuses, key=lambda s: _SEVERITY[s])


def assess_task(task_payload: dict[str, Any]) -> LayerAssessment:
    """LOGICAL_TASK: Phase 1 replay contract inputs present?"""
    required = ("template_id", "template_version", "seed", "generation_config", "engine_version")
    missing = [k for k in required if task_payload.get(k) is None]
    if missing:
        return LayerAssessment(
            status="UNKNOWN",
            reasons=["task replay inputs incomplete"],
            missing_evidence=[f"task.{k}" for k in missing],
        )
    return LayerAssessment(
        status="VERIFIED",
        reasons=["template/version/seed/config/engine-version pinned (Phase 1 contract)"],
    )


def assess_generation(
    candidate_payload: dict[str, Any],
    model_payload: dict[str, Any] | None,
    raw_artifact_present: bool,
) -> LayerAssessment:
    """CANDIDATE_TRACEABLE: origin reconstructable vs regenerable."""
    if not candidate_payload.get("candidate_id"):
        return LayerAssessment(
            status="UNKNOWN",
            reasons=["no candidate identity"],
            missing_evidence=["candidate.candidate_id"],
        )
    if not raw_artifact_present:
        return LayerAssessment(
            status="NON_REPLAYABLE",
            reasons=["original response artifact missing; origin cannot be retrieved"],
            missing_evidence=["raw_response artifact"],
        )
    if model_payload is not None and model_payload.get("deterministic_replay") is True:
        return LayerAssessment(
            status="VERIFIED",
            reasons=["serving stack guarantees deterministic replay; response preserved"],
        )
    return LayerAssessment(
        status="CONDITIONAL",
        reasons=[
            "origin reconstructable from preserved response artifact",
            "bit-for-bit regeneration not guaranteed (model nondeterminism)",
        ],
    )


def assess_execution(
    execution_payload: dict[str, Any], environment_present: bool
) -> LayerAssessment:
    """EXECUTION_REPRODUCIBLE: image/policy/fixture pinned?"""
    missing = []
    if not execution_payload.get("sandbox_image_digest"):
        missing.append("execution.sandbox_image_digest")
    if not execution_payload.get("sandbox_config_version"):
        missing.append("execution.sandbox_config_version")
    if not environment_present:
        missing.append("environment_snapshot")
    if missing:
        if execution_payload.get("sandbox_image_digest"):
            return LayerAssessment(
                status="CONDITIONAL",
                reasons=["container image pinned; host/daemon not pinned"],
                missing_evidence=missing,
            )
        return LayerAssessment(
            status="NOT_VERIFIED",
            reasons=["execution environment insufficiently pinned"],
            missing_evidence=missing,
        )
    return LayerAssessment(
        status="VERIFIED",
        reasons=["image digest, sandbox policy, fixture, and runtime versions pinned"],
    )


def assess_verification(
    verification_payload: dict[str, Any], verification_config_present: bool
) -> LayerAssessment:
    """VERIFICATION_REPRODUCIBLE: oracle + stage configs versioned?"""
    missing = []
    if verification_payload.get("oracle_version", 0) == 0 and not verification_payload.get(
        "oracle_strategy"
    ):
        missing.append("verification.oracle_version")
    if not verification_config_present:
        missing.append("verification_configuration")
    if missing:
        return LayerAssessment(
            status="NOT_VERIFIED",
            reasons=["verification configuration incomplete"],
            missing_evidence=missing,
        )
    return LayerAssessment(
        status="VERIFIED",
        reasons=["oracle version and stage configurations pinned (deterministic Python oracles)"],
    )


def assess_quality(
    quality_payload: dict[str, Any], quality_config_present: bool
) -> LayerAssessment:
    """QUALITY_REPRODUCIBLE: inputs, config, and selection rules pinned?"""
    missing = []
    if not quality_config_present:
        missing.append("quality_configuration")
    if not quality_payload.get("candidate_id"):
        missing.append("quality.candidate_id")
    if missing:
        return LayerAssessment(
            status="NOT_VERIFIED",
            reasons=["quality inputs incomplete"],
            missing_evidence=missing,
        )
    return LayerAssessment(
        status="VERIFIED",
        reasons=["quality inputs, config, and deterministic selection rules pinned"],
    )


def assess_dataset(snapshot_id: str | None, recomputed_id: str | None) -> LayerAssessment:
    """DATASET_REPRODUCIBLE: does the snapshot identity recompute?"""
    if not snapshot_id or not recomputed_id:
        return LayerAssessment(
            status="UNKNOWN",
            reasons=["snapshot identity unavailable"],
            missing_evidence=["dataset_snapshot_id"],
        )
    if snapshot_id == recomputed_id:
        return LayerAssessment(
            status="VERIFIED", reasons=["snapshot identity recomputes from members"]
        )
    return LayerAssessment(
        status="NOT_VERIFIED",
        reasons=[f"snapshot identity mismatch: {snapshot_id} != {recomputed_id}"],
    )


def assess_reproducibility(
    task_payload: dict[str, Any],
    candidate_payload: dict[str, Any],
    model_payload: dict[str, Any] | None,
    raw_artifact_present: bool,
    execution_payload: dict[str, Any],
    environment_present: bool,
    verification_payload: dict[str, Any],
    verification_config_present: bool,
    quality_payload: dict[str, Any],
    quality_config_present: bool,
    snapshot_id: str | None,
    recomputed_snapshot_id: str | None,
) -> ReproducibilityReport:
    """Assemble the full per-record reproducibility report."""
    layers = {
        "task_reproducibility": assess_task(task_payload),
        "generation_reproducibility": assess_generation(
            candidate_payload, model_payload, raw_artifact_present
        ),
        "execution_reproducibility": assess_execution(execution_payload, environment_present),
        "verification_reproducibility": assess_verification(
            verification_payload, verification_config_present
        ),
        "quality_reproducibility": assess_quality(quality_payload, quality_config_present),
        "dataset_reproducibility": assess_dataset(snapshot_id, recomputed_snapshot_id),
    }
    overall = worst_status([layer.status for layer in layers.values()])
    reasons = [f"{name}: {layer.status}" for name, layer in layers.items()]
    missing = [item for layer in layers.values() for item in layer.missing_evidence]
    return ReproducibilityReport(
        task_reproducibility=layers["task_reproducibility"],
        generation_reproducibility=layers["generation_reproducibility"],
        execution_reproducibility=layers["execution_reproducibility"],
        verification_reproducibility=layers["verification_reproducibility"],
        quality_reproducibility=layers["quality_reproducibility"],
        dataset_reproducibility=layers["dataset_reproducibility"],
        overall_status=overall,
        reasons=reasons,
        missing_evidence=missing,
        schema_version=PROVENANCE_SCHEMA_VERSION,
    )


def compare_reproduction(expected: dict[str, Any], actual: dict[str, Any]) -> ReproducibilityDiff:
    """Compare two reproduction manifests field by field (§47–§48).

    Categories follow the spec vocabulary (SOURCE_CHANGED, MODEL_CHANGED,
    ...). Identical manifests yield VERIFIED with no differences; any
    drift yields CONDITIONAL with structured entries. This is comparison
    and evidence — never automated replay.
    """
    differences: list[ReproducibilityDifference] = []

    def note(category: str, old: Any, new: Any) -> None:
        differences.append(
            ReproducibilityDifference(category=category, expected=str(old), actual=str(new))
        )

    expected_source = expected.get("source_snapshot", {}) or {}
    actual_source = actual.get("source_snapshot", {}) or {}
    if expected_source.get("git_commit") != actual_source.get("git_commit") or expected_source.get(
        "source_fingerprint"
    ) != actual_source.get("source_fingerprint"):
        note(
            "SOURCE_CHANGED",
            expected_source.get("source_fingerprint"),
            actual_source.get("source_fingerprint"),
        )
    if expected.get("dependency_snapshot") != actual.get("dependency_snapshot"):
        note(
            "DEPENDENCY_CHANGED",
            (expected.get("dependency_snapshot") or {}).get("dependency_lock_hash"),
            (actual.get("dependency_snapshot") or {}).get("dependency_lock_hash"),
        )

    def index_models(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {m.get("model_name", ""): m for m in manifest.get("model_snapshots", []) or []}

    expected_models, actual_models = index_models(expected), index_models(actual)
    for name in sorted(set(expected_models) | set(actual_models)):
        old, new = expected_models.get(name, {}), actual_models.get(name, {})
        if old.get("model_revision") != new.get("model_revision"):
            note("MODEL_CHANGED", old.get("model_revision"), new.get("model_revision"))
        if old.get("prompt_version") != new.get("prompt_version"):
            note("PROMPT_CHANGED", old.get("prompt_version"), new.get("prompt_version"))
        if old.get("generation_config") != new.get("generation_config"):
            note("GENERATION_CONFIG_CHANGED", name, name)

    def index_configs(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
        configs: dict[str, dict[str, Any]] = {}
        for config in manifest.get("configuration_snapshots", []) or []:
            configs[str(config.get("config_name", "")).split(":")[0]] = config
        return configs

    expected_configs, actual_configs = index_configs(expected), index_configs(actual)
    sandbox_old = expected_configs.get("sandbox", {})
    sandbox_new = actual_configs.get("sandbox", {})
    if sandbox_old.get("content_hash") != sandbox_new.get("content_hash"):
        note(
            "SANDBOX_POLICY_CHANGED",
            sandbox_old.get("content_hash"),
            sandbox_new.get("content_hash"),
        )
    verification_old = expected_configs.get("verification", {})
    verification_new = actual_configs.get("verification", {})
    if verification_old.get("content_hash") != verification_new.get("content_hash"):
        note(
            "VERIFICATION_CONFIG_CHANGED",
            verification_old.get("content_hash"),
            verification_new.get("content_hash"),
        )
    quality_old = expected_configs.get("quality", {})
    quality_new = actual_configs.get("quality", {})
    if quality_old.get("content_hash") != quality_new.get("content_hash"):
        note(
            "QUALITY_CONFIG_CHANGED",
            quality_old.get("content_hash"),
            quality_new.get("content_hash"),
        )

    expected_env = expected.get("environment_snapshot", {}) or {}
    actual_env = actual.get("environment_snapshot", {}) or {}
    if expected_env.get("container_image_digest") != actual_env.get("container_image_digest"):
        note(
            "SANDBOX_IMAGE_CHANGED",
            expected_env.get("container_image_digest"),
            actual_env.get("container_image_digest"),
        )

    def index_artifacts(manifest: dict[str, Any]) -> dict[str, str]:
        refs = manifest.get("artifact_refs", []) or []
        return {a.get("logical_name", ""): a.get("content_hash", "") for a in refs}

    expected_artifacts, actual_artifacts = index_artifacts(expected), index_artifacts(actual)
    for logical_name in sorted(set(expected_artifacts) | set(actual_artifacts)):
        if expected_artifacts.get(logical_name) != actual_artifacts.get(logical_name):
            note(
                "ARTIFACT_CHANGED",
                f"{logical_name}@{expected_artifacts.get(logical_name)}",
                f"{logical_name}@{actual_artifacts.get(logical_name)}",
            )

    if sorted(expected.get("golden_record_ids", []) or []) != sorted(
        actual.get("golden_record_ids", []) or []
    ):
        note(
            "DATASET_MEMBERSHIP_CHANGED",
            str(len(expected.get("golden_record_ids", []) or [])),
            str(len(actual.get("golden_record_ids", []) or [])),
        )

    return ReproducibilityDiff(
        status="VERIFIED" if not differences else "CONDITIONAL",
        differences=differences,
        schema_version=PROVENANCE_SCHEMA_VERSION,
    )
