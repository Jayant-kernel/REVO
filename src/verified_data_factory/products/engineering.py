"""Strict internal engineering export prerequisites and complete asset checks."""
from __future__ import annotations

import importlib.metadata
import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from verified_data_factory.generation.models import CandidateSolution, GenerationConfig
from verified_data_factory.local_paths import io_path
from verified_data_factory.quality.export import build_golden_record_id
from verified_data_factory.sandbox import SandboxExecutor, load_config
from verified_data_factory.task_engine.models import TaskInstance
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.models import VerificationConfig
from verified_data_factory.verification.readiness import qualify
from verified_data_factory.verification.verifier import verify_candidate

from .errors import ProductConfigError
from .manifest import read_checksums
from .models import ProductSchema, SplitPolicy
from .schemas import canonical_schema
from .serializers import hash_file


def check_source(golden: Any, quality: dict[str, Any], root: Path) -> None:
    evidence = quality.get("engineering_record")
    if not isinstance(evidence, dict):
        raise ProductConfigError("fresh engineering qualification record missing")
    if (evidence.get("contract_id"), evidence.get("contract_version")) != (golden.task.get("template_id"), golden.task.get("template_version")):
        raise ProductConfigError("engineering evidence contract/version mismatch")
    if not qualify(root, evidence)["eligible"]:
        raise ProductConfigError("engineering source qualification missing or stale")
    bound = build_golden_record_id(task=golden.task, instruction=golden.instruction, schema=golden.schema_,
                                   candidate_solution=golden.candidate_solution, record_schema_version=golden.record_schema_version)
    if bound != golden.record_id:
        raise ProductConfigError("engineering record identity is not content-bound")
    if golden.verification.get("verdict") != "PASS" or golden.verification.get("verification_strength") != "STRONG":
        raise ProductConfigError("engineering row lacks PASS/STRONG execution evidence")
    if golden.verification.get("mutation", {}).get("semantic_kills", 0) < 3:
        raise ProductConfigError("engineering row mutation evidence incomplete")
    task = TaskInstance.model_validate(golden.task)
    if golden.instruction != task.instruction or golden.schema_ != [t.model_dump(mode="json") for t in task.schema_]:
        raise ProductConfigError("engineering row instruction/schema differs from replay task")
    candidate = CandidateSolution(candidate_id=golden.candidate_id, task_id=task.task_id, model="engineering-replay",
        model_revision="no-generation", prompt_version="replay", generation_schema_version="1.0", provider="replay",
        endpoint_id="no-model", candidate_index=0, raw_response=golden.candidate_solution,
        candidate_sql=golden.candidate_solution, generation_config=GenerationConfig(seed=task.seed),
        generation_timestamp=datetime.now(UTC).isoformat(), generation_duration_ms=0)
    config = load_config(root / "configs/sandbox_production.yaml")
    execution = SandboxExecutor(config).execute(task, candidate)
    result = verify_candidate(task, candidate, execution, VerificationConfig(mutation_min_score=1.0), backend=DerivedTaskBackend(config))
    if (result.verdict != "PASS" or result.verification_strength != "STRONG"
            or result.mutation is None or result.mutation.survived or result.mutation.invalid or result.mutation.inconclusive):
        raise ProductConfigError("engineering row SQL failed fresh sandbox replay")


def check_assets(root: Path, manifest: Any, records: list[dict[str, Any]]) -> list[str]:
    errors = []
    if not records or manifest.record_count < 1:
        errors.append("empty engineering release")
    files = {entry.relative_path: entry for entry in manifest.files}
    if len(files) != len(manifest.files) or any(not (root / relative).resolve().is_relative_to(root.resolve()) for relative in files):
        return ["duplicate or unsafe engineering asset path"]
    if not {shard.relative_path for shard in manifest.shards} <= set(files):
        errors.append("shards missing from checksum-bound file inventory")
    required_assets = {"dataset_card.md", "preview.json", "schema.json", "split_policy.json", "engineering_dependencies.json",
                       "engineering_acceptance.json", "engineering_isolation.json"}
    required_assets.add("validate_engineering.py")
    if not required_assets <= set(files):
        errors.append("required engineering assets missing from checksum-bound inventory")
    sums_path = root / "SHA256SUMS"
    if not sums_path.exists():
        errors.append("complete SHA256SUMS required")
    else:
        try:
            sums = read_checksums(sums_path)
            if set(sums) != set(files) | {"manifest.json"}:
                errors.append("checksum inventory differs from declared files")
            if any(sums.get(relative) != hash_file(root / relative)[1] for relative in files):
                errors.append("engineering asset checksum mismatch")
            if sums.get("manifest.json") != hash_file(root / "manifest.json")[1]:
                errors.append("engineering manifest checksum mismatch")
        except (OSError, ValueError):
            errors.append("engineering checksum inventory unreadable")
    for name in ("dataset_card.md", "preview.json", "schema.json", "split_policy.json", "engineering_dependencies.json"):
        if not (root / name).is_file():
            errors.append(f"required engineering asset missing: {name}")
    try:
        schema = ProductSchema.model_validate(json.loads((root / "schema.json").read_text()))
        policy = SplitPolicy.model_validate(json.loads((root / "split_policy.json").read_text()))
        if schema != canonical_schema() or policy.group_by != "engineering_group" or not policy.require_group_isolation:
            errors.append("engineering schema/policy contract mismatch")
    except (OSError, ValueError):
        errors.append("engineering schema/policy unavailable or malformed")
    dependencies_path = root / "engineering_dependencies.json"
    if dependencies_path.exists():
        try:
            dependency = json.loads(dependencies_path.read_text())
            resolved_source = (root / dependency["bundled_root"]).resolve()
            if not resolved_source.is_relative_to(root.resolve()):
                raise ValueError("bundled dependency root missing or unsafe")
            source_root = io_path(resolved_source)
            if not source_root.is_dir():
                raise ValueError("bundled dependency root missing or unsafe")
            if not dependency["files"]:
                errors.append("empty engineering dependency manifest")
            if dependency.get("python_version") != platform.python_version() or not dependency.get("runtime_versions"):
                errors.append("engineering environment lock missing or changed")
            for name, version in dependency.get("runtime_versions", {}).items():
                if importlib.metadata.version(name) != version:
                    errors.append("engineering dependency version changed")
                    break
            for relative, checksum in dependency["files"].items():
                source = (source_root / relative).resolve()
                if not source.is_relative_to(source_root) or hash_file(source)[1] != checksum:
                    errors.append("engineering dependency changed or invalid path")
                    break
        except (OSError, KeyError, ValueError, TypeError, importlib.metadata.PackageNotFoundError):
            errors.append("engineering dependencies unavailable or invalid")
    for row in records:
        for name in ("instruction", "schema", "task_id", "golden_record_id", "dataset_snapshot_id"):
            if not isinstance(row.get(name), str) or not row[name]:
                errors.append(f"invalid engineering field: {name}")
        if row.get("dialect") != "DuckDB" or type(row.get("template_version")) is not int or row["template_version"] < 1:
            errors.append("engineering dialect/version type mismatch")
    preview = root / "preview.json"
    if preview.exists():
        try:
            json.loads(preview.read_text())
        except (OSError, ValueError):
            errors.append("engineering preview is not valid JSON")
    if not errors:
        from .acceptance import validate_acceptance
        errors.extend(validate_acceptance(root, manifest, records))
    return errors
