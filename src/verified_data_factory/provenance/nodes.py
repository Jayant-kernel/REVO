"""Provenance node builders (Phase 6).

Each builder takes a Phase 1–5 object and returns a content-addressed
:class:`ProvenanceNode`. Rules enforced here:

* payloads contain identity-bearing fields only — volatile run ids
  (``execution_id`` embeds a timestamp), timestamps, durations, and raw
  stdout/stderr NEVER enter a hashed payload. They remain available in
  the referenced raw artifacts and in activities.
* every nested mapping that could carry secrets passes through
  :func:`scrub_secrets` (provider metadata, env dumps, free-form details).
* builders never mutate their inputs.
"""

from __future__ import annotations

import re
from typing import Any

from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.quality.models import AuditSample, GoldenRecord, RecordQuality
from verified_data_factory.sandbox.models import ExecutionResult
from verified_data_factory.task_engine.models import TaskInstance
from verified_data_factory.verification.models import VerificationResult

from .canonical import canonical_bytes
from .hashing import content_id, hash_bytes
from .models import PROVENANCE_SCHEMA_VERSION, ModelSnapshot, NodeType, ProvenanceNode

_SECRET_KEY = re.compile(
    r"api[_-]?key|access[_-]?token|auth|bearer|secret|passwd|password|credential|"
    r"private[_-]?key|docker[_-]?config|ssh[_-]?key|session[_-]?token",
    re.IGNORECASE,
)


def scrub_secrets(value: Any) -> tuple[Any, int]:
    """Remove secret-valued keys at any depth. Returns (cleaned, redacted_count)."""
    redacted = 0
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and _SECRET_KEY.search(key):
                redacted += 1
                continue
            sub, count = scrub_secrets(item)
            redacted += count
            cleaned[key] = sub
        return cleaned, redacted
    if isinstance(value, list):
        out = []
        for item in value:
            sub, count = scrub_secrets(item)
            redacted += count
            out.append(sub)
        return out, redacted
    return value, 0


def make_node(node_type: NodeType, payload: Any) -> ProvenanceNode:
    """Build a content-addressed node (payload must already be scrubbed)."""
    clean, _ = scrub_secrets(payload)
    return ProvenanceNode(
        node_id=content_id(node_type, PROVENANCE_SCHEMA_VERSION, clean),
        node_type=node_type,
        schema_version=PROVENANCE_SCHEMA_VERSION,
        payload=clean if isinstance(clean, dict) else {"value": clean},
    )


def _sha_text(text: str) -> str:
    return hash_bytes(text.encode("utf-8"))


def task_instance_node(task: TaskInstance) -> ProvenanceNode:
    """TASK_INSTANCE — logical origin per the Phase 1 replay contract."""
    canonical_task = task.model_dump(mode="json", by_alias=True)
    payload = {
        "task_id": task.task_id,
        "template_id": task.template_id,
        "template_version": task.template_version,
        "seed": task.seed,
        "family": task.family,
        "difficulty": task.difficulty,
        "generation_config": task.generation_metadata.config,
        "engine_version": task.generation_metadata.engine_version,
        "canonical_task_hash": hash_bytes(canonical_bytes(canonical_task)),
        "instruction_hash": _sha_text(task.instruction),
        "fixture_hash": hash_bytes(
            canonical_bytes(
                {
                    "schema": task.model_dump(mode="json", by_alias=True)["schema"],
                    "tables": task.tables,
                }
            )
        ),
    }
    return make_node("TASK_INSTANCE", payload)


def candidate_solution_node(candidate: CandidateSolution) -> ProvenanceNode:
    """CANDIDATE_SOLUTION — exact response preserved by hash, never rewritten."""
    config = candidate.generation_config.model_dump(mode="json")
    payload = {
        "candidate_id": candidate.candidate_id,
        "task_id": candidate.task_id,
        "model": candidate.model,
        "model_revision": candidate.model_revision,
        "prompt_version": candidate.prompt_version,
        "generation_schema_version": candidate.generation_schema_version,
        "provider": candidate.provider,
        "endpoint_id": candidate.endpoint_id,
        "candidate_index": candidate.candidate_index,
        "generation_config": config,
        "raw_response_hash": _sha_text(candidate.raw_response),
        "candidate_sql_hash": _sha_text(candidate.candidate_sql or ""),
        "finish_reason": candidate.finish_reason,
        "generation_status": candidate.generation_status,
        "parse_status": candidate.parse_status,
        "token_usage": candidate.token_usage.model_dump(mode="json")
        if candidate.token_usage
        else None,
        "provider_metadata": candidate.provider_metadata,
    }
    return make_node("CANDIDATE_SOLUTION", payload)


def execution_result_node(execution: ExecutionResult) -> ProvenanceNode:
    """EXECUTION_RESULT — what happened, sans logs and timings."""
    result_data = execution.result_data.model_dump(mode="json") if execution.result_data else None
    payload = {
        "task_id": execution.task_id,
        "candidate_id": execution.candidate_id,
        "status": execution.status,
        "failure_code": execution.failure.code if execution.failure else None,
        "failure_message": execution.failure.message if execution.failure else None,
        "result_hash": hash_bytes(canonical_bytes(result_data))
        if result_data is not None
        else None,
        "rows_returned": execution.result_data.rows_returned if execution.result_data else 0,
        "truncated": execution.result_data.truncated if execution.result_data else False,
        "exit_code": execution.exit_code,
        "resource_limits": execution.resource_limits.model_dump(mode="json"),
        "sandbox_image": execution.sandbox_image,
        "sandbox_image_digest": execution.sandbox_image_digest,
        "sandbox_config_version": execution.sandbox_config_version,
        "duckdb_version": execution.duckdb_version,
        "stdout_hash": _sha_text(execution.stdout),
        "stderr_hash": _sha_text(execution.stderr),
    }
    return make_node("EXECUTION_RESULT", payload)


def verification_result_node(verification: VerificationResult) -> ProvenanceNode:
    """VERIFICATION_RESULT — verdict evidence, never recalculated here."""
    oracle = verification.oracle.model_dump(mode="json") if verification.oracle else None
    if isinstance(oracle, dict):
        oracle.pop("runtime_ms", None)
    performance = (
        verification.performance.model_dump(mode="json") if verification.performance else None
    )
    if isinstance(performance, dict):
        performance.pop("duration_ms", None)
    payload = {
        "task_id": verification.task_id,
        "candidate_id": verification.candidate_id,
        "verdict": verification.verdict,
        "failure_code": verification.failure_code,
        "verification_strength": verification.verification_strength,
        "oracle_version": verification.oracle_version,
        "oracle_strategy": (oracle or {}).get("strategy"),
        "mutation_score": (
            verification.mutation.model_dump(mode="json") if verification.mutation else {}
        ).get("mutation_score"),
        "stage_evidence_hash": hash_bytes(
            canonical_bytes(
                {
                    "comparison": verification.comparison.model_dump(mode="json")
                    if verification.comparison
                    else None,
                    "hidden": verification.hidden.model_dump(mode="json")
                    if verification.hidden
                    else None,
                    "properties": verification.properties.model_dump(mode="json")
                    if verification.properties
                    else None,
                    "metamorphic": verification.metamorphic.model_dump(mode="json")
                    if verification.metamorphic
                    else None,
                    "mutation": verification.mutation.model_dump(mode="json")
                    if verification.mutation
                    else None,
                }
            )
        ),
        "verification_config_version": verification.verification_config_version,
        "oracle": oracle,
        "performance": performance,
    }
    return make_node("VERIFICATION_RESULT", payload)


def record_quality_node(quality: RecordQuality) -> ProvenanceNode:
    """RECORD_QUALITY — Phase 5 evidence restated by reference, not rerun."""
    payload = {
        "candidate_id": quality.candidate_id,
        "task_id": quality.task_id,
        "template_id": quality.template_id,
        "template_version": quality.template_version,
        "family": quality.family,
        "decision": quality.decision,
        "decision_reasons": list(quality.decision_reasons),
        "task_valid": quality.task_quality.valid,
        "verification_verdict": quality.verification.verdict,
        "verification_strength": quality.verification.verification_strength,
        "mutation_score": quality.verification.mutation_score,
        "duplicate_groups": {
            "exact": quality.exact_duplicate_group,
            "structural": quality.structural_duplicate_group,
            "semantic": quality.semantic_duplicate_group,
        },
        "contamination_flags": [f.model_dump(mode="json") for f in quality.contamination_flags],
        "audit_required": quality.audit_required,
        "audit_status": quality.audit_status,
        "auditor_result": quality.auditor_result,
        "role": quality.role,
    }
    return make_node("RECORD_QUALITY", payload)


def golden_record_node(golden: GoldenRecord) -> ProvenanceNode:
    """GOLDEN_RECORD — canonical Golden content hash plus key references."""
    content = golden.model_dump(mode="json", by_alias=True)
    payload = {
        "record_id": golden.record_id,
        "candidate_id": golden.candidate_id,
        "golden_content_hash": hash_bytes(canonical_bytes(content)),
        "dataset_role": golden.dataset_role,
        "audit_status": golden.audit_status,
        "instruction_hash": _sha_text(golden.instruction),
        "candidate_sql_hash": _sha_text(golden.candidate_solution),
    }
    return make_node("GOLDEN_RECORD", payload)


def audit_sample_node(sample: AuditSample) -> ProvenanceNode:
    """AUDIT_SAMPLE — sampled ids plus policy (seed), never reviewer secrets."""
    payload = {
        "selection_seed": sample.selection_seed,
        "sampled_count": sample.sampled_count,
        "sampled_candidate_ids": sorted(i.candidate_id for i in sample.items),
    }
    return make_node("AUDIT_SAMPLE", payload)


def audit_result_node(candidate_id: str, result: str | None, note: str = "") -> ProvenanceNode:
    """AUDIT_RESULT — decision only (reviewer identity only if provided)."""
    return make_node(
        "AUDIT_RESULT",
        {"candidate_id": candidate_id, "result": result, "note": note},
    )


def _model_family(model_name: str) -> str | None:
    lowered = model_name.lower()
    for family in ("qwen", "devstral", "deepseek", "llama", "mistral", "codestral"):
        if family in lowered:
            return family
    return None


def capture_model_snapshot(
    candidate: CandidateSolution,
    license_identifier: str | None = None,
    source_registry: str | None = None,
    deterministic_replay: bool = False,
) -> ModelSnapshot:
    """Snapshot model origin from a candidate.

    Safe origin metadata only; license/source recorded verbatim when the
    upstream system provides them — never inferred, no commercial
    conclusions. Unless the serving stack guarantees determinism,
    ``deterministic_replay`` stays False and the original response
    artifact remains the ground truth.
    """
    payload = {
        "provider": candidate.provider,
        "model_name": candidate.model,
        "model_revision": candidate.model_revision,
        "model_family": _model_family(candidate.model),
        "license_identifier": license_identifier,
        "source_registry": source_registry,
        "endpoint_identifier_hash": candidate.endpoint_id,
        "generation_config": candidate.generation_config.model_dump(mode="json"),
        "prompt_version": candidate.prompt_version,
        "generation_schema_version": candidate.generation_schema_version,
        "deterministic_replay": deterministic_replay,
    }
    return ModelSnapshot(
        model_snapshot_id=content_id("MODEL_SNAPSHOT", PROVENANCE_SCHEMA_VERSION, payload),
        provider=payload["provider"],
        model_name=payload["model_name"],
        model_revision=payload["model_revision"],
        model_family=payload["model_family"],
        license_identifier=payload["license_identifier"],
        source_registry=payload["source_registry"],
        endpoint_identifier_hash=payload["endpoint_identifier_hash"],
        generation_config=payload["generation_config"],
        prompt_version=payload["prompt_version"],
        generation_schema_version=payload["generation_schema_version"],
        deterministic_replay=payload["deterministic_replay"],
        schema_version=PROVENANCE_SCHEMA_VERSION,
    )
