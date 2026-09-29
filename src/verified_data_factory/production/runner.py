"""Checkpointing orchestrator for an authorized future production run.

It composes the Phase 1–5 public APIs; it has no alternate verifier, sandbox,
or quality implementation. Calling it requires an explicit execution flag.
"""
from __future__ import annotations

import json
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from verified_data_factory.generation import GenerationConfig, create_provider, generate_candidates
from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.quality import analyze_dataset, export_dataset, load_quality_config
from verified_data_factory.quality.models import VerifiedRecord
from verified_data_factory.sandbox import SandboxExecutor
from verified_data_factory.sandbox import load_config as load_sandbox_config
from verified_data_factory.sandbox.models import ExecutionResult
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.export import read_jsonl
from verified_data_factory.verification import verification_from_dict, verify_candidate

from . import api as production_api
from .api import assert_resume_config, config_id
from .errors import ProductionConfigError
from .models import FAMILIES, ProductionConfig


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line] if path.exists() else []


def _append(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _write_state(root: Path, payload: dict[str, object]) -> None:
    path = root / "manifests/run-state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _pause_reason(
    config: ProductionConfig,
    records: Sequence[VerifiedRecord],
    qualities: Sequence[object],
) -> str | None:
    if not records:
        return None
    limits = config.pause_conditions
    total = len(records)
    execution_error_rate = sum(r.execution.status != "SUCCEEDED" for r in records) / total
    inconclusive_rate = sum(r.verification.verdict == "INCONCLUSIVE" for r in records) / total
    semantic_duplicate_rate = sum(
        getattr(q, "semantic_duplicate_group", None) is not None for q in qualities
    ) / max(1, len(qualities))
    measured = {
        "execution_error_rate": execution_error_rate,
        "inconclusive_rate": inconclusive_rate,
        "semantic_duplicate_rate": semantic_duplicate_rate,
    }
    for name, value in measured.items():
        if name in limits and value > float(limits[name]):
            return f"{name}={value:.4f} exceeds {float(limits[name]):.4f}"
    zero_limit = int(limits.get("zero_golden_attempts", 0))
    if zero_limit and len(qualities) >= zero_limit:
        recent = qualities[-zero_limit:]
        if all(getattr(q, "decision", None) != "GOLDEN" for q in recent):
            return f"zero Golden records in the latest {zero_limit} attempts"
    return None


def run_authorized(config: ProductionConfig, run_dir: str | Path, *, execute: bool = False) -> None:
    """Run/resume one frozen configuration only after explicit authorization."""
    if not execute:
        raise ProductionConfigError("production execution requires explicit authorization")
    root = Path(run_dir)
    configured_root = Path(config.output_dir)
    if root.resolve() != configured_root.resolve():
        raise ProductionConfigError(
            "run destination must match the frozen output_dir: "
            f"expected {configured_root}, received {root}"
        )
    if sum(config.family_distribution.values()) != config.initial_task_batch:
        raise ProductionConfigError("family distribution does not match initial_task_batch")
    readiness = production_api.preflight(config)
    if not readiness["ok"]:
        failed = sorted(
            name
            for name, result in readiness.get("checks", {}).items()
            if not result.get("ok", False)
        )
        raise ProductionConfigError(
            "production preflight failed: " + ", ".join(failed or ["unknown check"])
        )
    started = time.monotonic()
    manifest_path = root / "manifests/run-manifest.json"
    if manifest_path.exists():
        assert_resume_config(config, manifest_path)
    else:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "production_config_id": config_id(config),
                    "run_name": config.run_name,
                    "config_version": config.config_version,
                    "model_id": config.model.model_id,
                    "model_revision": config.model.model_revision,
                    "provider": config.model.provider,
                    "endpoint": config.model.endpoint,
                    "prompt_version": config.model.prompt_version,
                    "governance_status": config.model.governance_status,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    task_path, candidate_path = root / "tasks/tasks.jsonl", root / "candidates/candidates.jsonl"
    registry = load_builtin_registry()
    provider = create_provider(
        config.model.provider,
        base_url=config.model.endpoint,
        model_id=config.model.model_id,
        model_revision=config.model.model_revision,
    )
    sampling = GenerationConfig(temperature=config.model.temperature, top_p=config.model.top_p, max_tokens=config.model.max_tokens)
    triple_path = root / "execution/triples.jsonl"
    executor = SandboxExecutor(load_sandbox_config(config.sandbox_config))
    verification_path = root / "verification/verification.jsonl"
    state_path = root / "manifests/run-state.json"
    start_batch_index = 0
    if state_path.exists():
        previous_state = json.loads(state_path.read_text(encoding="utf-8"))
        previous_status = previous_state.get("status")
        previous_batch = int(previous_state.get("batch", 0))
        if previous_status == "AWAITING_BATCH_AUTHORIZATION":
            start_batch_index = previous_batch
        elif previous_status == "RUNNING":
            start_batch_index = max(0, previous_batch - 1)
        else:
            raise ProductionConfigError(
                f"run state {previous_status!r} cannot continue automatically; human review is required"
            )
    elif task_path.exists():
        existing_task_count = len(read_jsonl(task_path))
        if existing_task_count:
            start_batch_index = (existing_task_count - 1) // config.initial_task_batch
    for batch_index in range(
        start_batch_index,
        min(start_batch_index + config.batches_per_authorization, config.max_batches),
    ):
        _write_state(root, {"status": "RUNNING", "batch": batch_index + 1})
        elapsed_minutes = (time.monotonic() - started) / 60
        if elapsed_minutes >= config.budget.max_wall_time_minutes:
            _write_state(root, {"status": "PAUSED", "reason": "wall-time budget reached", "batch": batch_index})
            return
        tasks = read_jsonl(task_path) if task_path.exists() else []
        existing_batches = max(0, len(tasks) // config.initial_task_batch)
        if batch_index >= existing_batches:
            if len(tasks) + config.initial_task_batch > config.budget.max_total_tasks:
                _write_state(root, {"status": "PAUSED", "reason": "task budget reached", "batch": batch_index})
                return
            if (len(tasks) + config.initial_task_batch) * config.candidates_per_task > config.budget.max_total_candidates:
                _write_state(root, {"status": "PAUSED", "reason": "candidate budget would be exceeded", "batch": batch_index})
                return
            new_tasks = []
            for family_index, family in enumerate(FAMILIES):
                template = max(registry.list_by_family(family), key=lambda item: item.version)
                for index in range(config.family_distribution[family]):
                    seed = config.seed + batch_index * 1_000_000 + family_index * 100_000 + index
                    new_tasks.append(generate_task(template, seed))
            task_path.parent.mkdir(parents=True, exist_ok=True)
            with task_path.open("a", encoding="utf-8") as handle:
                for task in new_tasks:
                    handle.write(task.model_dump_json(by_alias=True) + "\n")
            tasks.extend(new_tasks)
        task_by_id = {task.task_id: task for task in tasks}
        batch_tasks = tasks[batch_index * config.initial_task_batch : (batch_index + 1) * config.initial_task_batch]
        completed_tasks = {row["task_id"] for row in _jsonl(candidate_path)}
        for task in batch_tasks:
            if task.task_id in completed_tasks:
                continue
            results = generate_candidates(task, [provider], sampling, config.candidates_per_task)
            _append(candidate_path, {"task_id": task.task_id, "family": task.family, "batch": batch_index + 1, "results": [result.model_dump(mode="json") for result in results]})
        bundles = _jsonl(candidate_path)
        candidates = [item for bundle in bundles for item in bundle["results"] if item.get("candidate_solution")]
        if len(candidates) > config.budget.max_total_candidates:
            raise ProductionConfigError("candidate cap exceeded despite pre-generation guard")
        executed = {row["candidate"]["candidate_id"] for row in _jsonl(triple_path)}
        for item in candidates:
            candidate = CandidateSolution.model_validate(item["candidate_solution"])
            if candidate.candidate_id in executed:
                continue
            execution = executor.execute(task_by_id[candidate.task_id], candidate)
            _append(triple_path, {"task": task_by_id[candidate.task_id].model_dump(mode="json", by_alias=True), "candidate": candidate.model_dump(mode="json", by_alias=True), "execution": execution.model_dump(mode="json")})
        existing = {row["candidate_id"] for row in _jsonl(verification_path)}
        for triple in _jsonl(triple_path):
            candidate = CandidateSolution.model_validate(triple["candidate"])
            if candidate.candidate_id in existing:
                continue
            verdict = verify_candidate(task_by_id[candidate.task_id], candidate, ExecutionResult.model_validate(triple["execution"]))
            _append(verification_path, verdict.model_dump(mode="json"))
        verdicts = {row["candidate_id"]: row for row in _jsonl(verification_path)}
        records = [
            VerifiedRecord(task=task_by_id[row["candidate"]["task_id"]], candidate=CandidateSolution.model_validate(row["candidate"]), execution=ExecutionResult.model_validate(row["execution"]), verification=verification_from_dict(verdicts[row["candidate"]["candidate_id"]]))
            for row in _jsonl(triple_path)
            if row["candidate"]["candidate_id"] in verdicts
        ]
        quality_config = load_quality_config(config.quality_config)
        quality_config = quality_config.model_copy(
            update={
                "audit_rate": min(1.0, config.audit.sample_size / max(1, len(records))),
                "audit_seed": config.audit.seed,
            }
        )
        analysis = analyze_dataset(records, quality_config)
        export_dataset(analysis.qualities, {record.candidate.candidate_id: record for record in records}, analysis.health.model_dump(mode="json"), [item.model_dump(mode="json") for item in analysis.audit_sample.items], root / "quality/export")
        golden_count = sum(q.decision == "GOLDEN" for q in analysis.qualities)
        state = {"status": "RUNNING", "batch": batch_index + 1, "tasks": len(tasks), "candidates": len(candidates), "golden": golden_count, "target": config.target_golden_records}
        _write_state(root, state)
        if golden_count >= config.target_golden_records:
            _write_state(root, {**state, "status": "TARGET_REACHED"})
            return
        reason = _pause_reason(config, records, analysis.qualities)
        if reason:
            _write_state(root, {**state, "status": "PAUSED", "reason": reason})
            return
        if batch_index + 1 >= config.max_batches:
            _write_state(root, {**state, "status": "MAX_BATCHES_REACHED"})
            return
        _write_state(
            root,
            {
                **state,
                "status": "AWAITING_BATCH_AUTHORIZATION",
                "reason": "one authorized batch completed; review results before continuing",
            },
        )
        return
    _write_state(root, {"status": "MAX_BATCHES_REACHED", "batch": config.max_batches, "target": config.target_golden_records})
