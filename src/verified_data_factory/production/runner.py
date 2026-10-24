"""Checkpointing orchestrator for an authorized future production run.

It composes the Phase 1–5 public APIs; it has no alternate verifier, sandbox,
or quality implementation. Calling it requires an explicit execution flag.
"""
from __future__ import annotations

import hashlib
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
from verified_data_factory.verification.backend import DerivedTaskBackend

from . import api as production_api
from .api import ContractReadiness, assert_resume_config, config_id
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
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


_CHECKPOINT_FILES = ("tasks/tasks.jsonl", "candidates/attempt-reservations.jsonl", "candidates/candidates.jsonl",
                     "execution/triples.jsonl", "verification/verification.jsonl")


def _artifact_hashes(root: Path) -> dict[str, str]:
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in _CHECKPOINT_FILES if (root / name).exists()}


def _checkpoint(root: Path, payload: dict[str, object]) -> None:
    _write_state(root, {**payload, "artifact_hashes": _artifact_hashes(root)})


def _assert_checkpoint_integrity(root: Path, state: dict[str, Any]) -> None:
    if "artifact_hashes" not in state or state["artifact_hashes"] != _artifact_hashes(root):
        raise ProductionConfigError("checkpoint artifacts changed or are unpinned; preserve evidence and use a new run identity")


def _reserve_attempts(root: Path, task_id: str, config: ProductionConfig) -> bool:
    """Charge interrupted generation too, before invoking the provider.

    A reservation is a conservative bound on logical candidate attempts, not
    an assertion that an interrupted request actually produced a response.
    Transport retries remain separately governed by the provider's limits.
    """
    path = root / "candidates/attempt-reservations.jsonl"
    reserved = sum(int(row["attempts"]) for row in _jsonl(path))
    if reserved + config.candidates_per_task > config.budget.max_total_candidates:
        return False
    _append(path, {"task_id": task_id, "attempts": config.candidates_per_task})
    return True


def _check_budget(root: Path, started: float, prior_seconds: float, config: ProductionConfig) -> bool:
    """Check between bounded calls in every expensive phase, also across resume."""
    elapsed = prior_seconds + time.monotonic() - started
    if elapsed < config.budget.max_wall_time_minutes * 60:
        return True
    state_path = root / "manifests/run-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    _checkpoint(root, {**state, "status": "PAUSED", "reason": "wall-time budget reached",
                        "elapsed_seconds": elapsed})
    return False


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
    from verified_data_factory.quality.population_metrics import (
        cross_task_semantic_duplicate_rate,
    )

    # The stop monitors repeated *tasks* across semantic groups. Multiple
    # generated candidates for one task are expected and must not stop a batch.
    semantic_duplicate_rate = cross_task_semantic_duplicate_rate(qualities)
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


def _effective_audit_rate(config: ProductionConfig, record_count: int) -> float:
    """Full review pools select automated survivors before human decisions."""
    if config.review_pool_mode:
        return 0.0
    return min(1.0, config.audit.sample_size / max(1, record_count))


def _latest_templates_for_family(registry: Any, family: str) -> list[Any]:
    """One current version per distinct business template, in stable order."""
    latest: dict[str, Any] = {}
    for template in registry.list_by_family(family):
        previous = latest.get(template.template_id)
        if previous is None or template.version > previous.version:
            latest[template.template_id] = template
    if not latest:
        raise ProductionConfigError(f"no task templates registered for family {family}")
    return [latest[template_id] for template_id in sorted(latest)]


def _template_catalog_id(registry: Any) -> str:
    """Bind a run to the full content of every selectable template."""
    payload = {
        family: [template.model_dump(mode="json") for template in _latest_templates_for_family(registry, family)]
        for family in FAMILIES
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _scheduled_templates(
    config: ProductionConfig, registry: Any, family: str, batch_index: int
) -> list[Any]:
    """Select each family's templates while retaining the frozen legacy path."""
    count = config.family_distribution[family]
    templates = _latest_templates_for_family(registry, family)
    if config.schedule_mode == "legacy":
        return [
            templates[(batch_index * count + index) % len(templates)]
            for index in range(count)
        ]
    selected = {template.template_id: template for template in templates}
    contract_ids = sorted(config.selected_contract_ids[family])
    return [selected[contract_id] for contract_id in contract_ids[:count]]


def run_authorized(
    config: ProductionConfig,
    run_dir: str | Path,
    *,
    execute: bool = False,
    contract_readiness: ContractReadiness | None = None,
    readiness_manifest: str | Path | None = None,
) -> None:
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
    readiness = production_api.preflight(
        config,
        contract_readiness=contract_readiness,
        readiness_manifest=readiness_manifest,
    )
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
    registry = load_builtin_registry()
    template_catalog_id = _template_catalog_id(registry)
    manifest_path = root / "manifests/run-manifest.json"
    source_id = production_api.implementation_id()
    if manifest_path.exists():
        assert_resume_config(config, manifest_path)
        frozen_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if frozen_manifest.get("template_catalog_id") != template_catalog_id:
            raise ProductionConfigError("task template catalog changed; use a new run identity")
        if frozen_manifest.get("implementation_id") != source_id:
            raise ProductionConfigError("executable source changed or unpinned; use a new run identity")
    else:
        if root.exists() and any(root.iterdir()):
            raise ProductionConfigError("nonempty run directory has no frozen manifest; use a new run identity")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(
                {
                    "production_config_id": config_id(config),
                    "policy_file_hashes": production_api.policy_file_hashes(config),
                    "template_catalog_id": template_catalog_id,
                    "implementation_id": source_id,
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
    provider = create_provider(
        config.model.provider,
        base_url=config.model.endpoint,
        model_id=config.model.model_id,
        model_revision=config.model.model_revision,
    )
    sampling = GenerationConfig(temperature=config.model.temperature, top_p=config.model.top_p, max_tokens=config.model.max_tokens)
    triple_path = root / "execution/triples.jsonl"
    sandbox_config = load_sandbox_config(config.sandbox_config)
    executor = SandboxExecutor(sandbox_config)
    verification_backend = DerivedTaskBackend(sandbox_config)
    verification_path = root / "verification/verification.jsonl"
    state_path = root / "manifests/run-state.json"
    start_batch_index = 0
    prior_seconds = 0.0
    if state_path.exists():
        previous_state = json.loads(state_path.read_text(encoding="utf-8"))
        _assert_checkpoint_integrity(root, previous_state)
        prior_seconds = float(previous_state.get("elapsed_seconds", 0))
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
        _checkpoint(root, {"status": "RUNNING", "batch": batch_index + 1,
                            "elapsed_seconds": prior_seconds})
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
                for index, template in enumerate(_scheduled_templates(config, registry, family, batch_index)):
                    seed = config.seed + batch_index * 1_000_000 + family_index * 100_000 + index
                    new_tasks.append(generate_task(template, seed))
            task_path.parent.mkdir(parents=True, exist_ok=True)
            # Publish the whole deterministic task batch atomically; interrupted
            # append previously allowed partial batches to be duplicated on resume.
            temporary = task_path.with_suffix(".tmp")
            with temporary.open("w", encoding="utf-8") as handle:
                for task in [*tasks, *new_tasks]:
                    handle.write(task.model_dump_json(by_alias=True) + "\n")
            temporary.replace(task_path)
            tasks.extend(new_tasks)
            _checkpoint(root, {"status": "RUNNING", "batch": batch_index + 1,
                               "elapsed_seconds": prior_seconds + time.monotonic() - started})
        task_by_id = {task.task_id: task for task in tasks}
        batch_tasks = tasks[batch_index * config.initial_task_batch : (batch_index + 1) * config.initial_task_batch]
        completed_tasks = {row["task_id"] for row in _jsonl(candidate_path)}
        for task in batch_tasks:
            if task.task_id in completed_tasks:
                continue
            if not _check_budget(root, started, prior_seconds, config):
                return
            if not _reserve_attempts(root, task.task_id, config):
                _checkpoint(root, {"status": "PAUSED", "batch": batch_index + 1,
                                   "reason": "candidate attempt reservation budget reached",
                                   "elapsed_seconds": prior_seconds + time.monotonic() - started})
                return
            _checkpoint(root, {"status": "RUNNING", "batch": batch_index + 1,
                               "elapsed_seconds": prior_seconds + time.monotonic() - started})
            results = generate_candidates(task, [provider], sampling, config.candidates_per_task)
            _append(candidate_path, {"task_id": task.task_id, "family": task.family, "batch": batch_index + 1, "results": [result.model_dump(mode="json") for result in results]})
            _checkpoint(root, {"status": "RUNNING", "batch": batch_index + 1,
                                "elapsed_seconds": prior_seconds + time.monotonic() - started})
        bundles = _jsonl(candidate_path)
        candidates = [item for bundle in bundles for item in bundle["results"] if item.get("candidate_solution")]
        if len(candidates) > config.budget.max_total_candidates:
            raise ProductionConfigError("candidate cap exceeded despite pre-generation guard")
        executed = {row["candidate"]["candidate_id"] for row in _jsonl(triple_path)}
        for item in candidates:
            candidate = CandidateSolution.model_validate(item["candidate_solution"])
            if candidate.candidate_id in executed:
                continue
            if not _check_budget(root, started, prior_seconds, config):
                return
            execution = executor.execute(task_by_id[candidate.task_id], candidate)
            _append(triple_path, {"task": task_by_id[candidate.task_id].model_dump(mode="json", by_alias=True), "candidate": candidate.model_dump(mode="json", by_alias=True), "execution": execution.model_dump(mode="json")})
            _checkpoint(root, {"status": "RUNNING", "batch": batch_index + 1,
                               "elapsed_seconds": prior_seconds + time.monotonic() - started})
        existing = {row["candidate_id"] for row in _jsonl(verification_path)}
        for triple in _jsonl(triple_path):
            candidate = CandidateSolution.model_validate(triple["candidate"])
            if candidate.candidate_id in existing:
                continue
            if not _check_budget(root, started, prior_seconds, config):
                return
            verdict = verify_candidate(task_by_id[candidate.task_id], candidate, ExecutionResult.model_validate(triple["execution"]), backend=verification_backend)
            _append(verification_path, verdict.model_dump(mode="json"))
            _checkpoint(root, {"status": "RUNNING", "batch": batch_index + 1,
                               "elapsed_seconds": prior_seconds + time.monotonic() - started})
        verdicts = {row["candidate_id"]: row for row in _jsonl(verification_path)}
        records = [
            VerifiedRecord(task=task_by_id[row["candidate"]["task_id"]], candidate=CandidateSolution.model_validate(row["candidate"]), execution=ExecutionResult.model_validate(row["execution"]), verification=verification_from_dict(verdicts[row["candidate"]["candidate_id"]]))
            for row in _jsonl(triple_path)
            if row["candidate"]["candidate_id"] in verdicts
        ]
        quality_config = load_quality_config(config.quality_config)
        quality_config = quality_config.model_copy(
            update={
                "audit_rate": _effective_audit_rate(config, len(records)),
                "audit_seed": config.audit.seed,
            }
        )
        analysis = analyze_dataset(records, quality_config)
        export_dataset(analysis.qualities, {record.candidate.candidate_id: record for record in records}, analysis.health.model_dump(mode="json"), [item.model_dump(mode="json") for item in analysis.audit_sample.items], root / "quality/export")
        from verified_data_factory.quality.population_metrics import population_duplicate_report

        (root / "quality/export/population_metrics.json").write_text(
            json.dumps(population_duplicate_report(analysis.qualities, records), indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        if config.review_pool_mode:
            # Automated survivors are review candidates. The human audit
            # remains pending and PUBLIC release validation requires its
            # separate frozen, independent-review package.
            golden_rows = _jsonl(root / "quality/export/golden.jsonl")
            queue_path = root / "quality/export/review_queue.jsonl"
            with queue_path.open("w", encoding="utf-8") as handle:
                for row in golden_rows:
                    handle.write(
                        json.dumps(
                            {
                                "record_id": row["record_id"],
                                "candidate_id": row["candidate_id"],
                                "family": row["quality"]["family"],
                                "status": "PENDING",
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )
        golden_count = sum(q.decision == "GOLDEN" for q in analysis.qualities)
        state = {"status": "RUNNING", "batch": batch_index + 1, "tasks": len(tasks), "candidates": len(candidates), "golden": golden_count, "target": config.target_golden_records,
                 "elapsed_seconds": prior_seconds + time.monotonic() - started}
        if config.review_pool_mode:
            state["human_review_status"] = "PENDING"
        _checkpoint(root, state)
        reason = _pause_reason(config, records, analysis.qualities)
        if reason:
            _checkpoint(root, {**state, "status": "PAUSED", "reason": reason})
            return
        if golden_count >= config.target_golden_records:
            _checkpoint(root, {**state, "status": "TARGET_REACHED"})
            return
        if batch_index + 1 >= config.max_batches:
            _checkpoint(root, {**state, "status": "MAX_BATCHES_REACHED"})
            return
        _checkpoint(
            root,
            {
                **state,
                "status": "AWAITING_BATCH_AUTHORIZATION",
                "reason": "one authorized batch completed; review results before continuing",
            },
        )
        return
    _write_state(root, {"status": "MAX_BATCHES_REACHED", "batch": config.max_batches, "target": config.target_golden_records})
