"""Phase 13 authorized scratch-only four-arm funnel generation experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from verified_data_factory.generation import (
    CandidateSolution,
    GenerationConfig,
    build_candidate_id,
    build_sql_prompt,
    create_provider,
    extract_candidate_sql,
)
from verified_data_factory.generation.errors import GenerationError
from verified_data_factory.sandbox import SandboxExecutor
from verified_data_factory.sandbox import load_config as load_sandbox_config
from verified_data_factory.sandbox.errors import SandboxError
from verified_data_factory.task_engine import generate_task, load_builtin_registry, validate_task
from verified_data_factory.verification import verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.errors import VerificationError

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "scratch" / "funnel-generation-experiment" / "authorized-20261003-four-arm"
MANIFEST = ROOT / "manifests" / "phase3-contract-readiness.json"
CAP_SECONDS, PROVIDER_TIMEOUT = 10_800, 180.0
ARMS = (
    ("pinned-baseline", "devstral", "alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest", "a2d26ea0b96b7a40afd673158d5cf44de25eff07fc8abf835e2cde5444632bc4"),
    ("pinned-feedback", "devstral", "alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest", "a2d26ea0b96b7a40afd673158d5cf44de25eff07fc8abf835e2cde5444632bc4"),
    ("qwen-baseline", "qwen", "mdq100/Qwen3-Coder-30B-A3B-Instruct:30b", "88cc37b8585d9ce9df3193b9624a7792c1fd9177c397e90c675b9370349aaad5"),
    ("qwen-feedback", "qwen", "mdq100/Qwen3-Coder-30B-A3B-Instruct:30b", "88cc37b8585d9ce9df3193b9624a7792c1fd9177c397e90c675b9370349aaad5"),
)
OUT = ROOT / "scratch" / "funnel-generation-experiment" / "phase13-authorized-current-runner-20261006-r3"
SEEDS = {"sql.funnel.saas_activation_payment": 104106}


def stamp() -> str:
    return datetime.now(UTC).isoformat()


def append(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def load_rows(out: Path) -> list[dict[str, Any]]:
    path = out / "calls.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def seed(arm: str, contract: str, index: int, retry: int) -> int:
    return int(hashlib.sha256(f"{arm}|{contract}|{index}|{retry}".encode()).hexdigest()[:12], 16)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pre_call_lock(contracts: list[str]) -> None:
    """Write immutable inputs before any provider is constructed."""
    task_source = ROOT / "templates" / "sql" / "funnel" / "saas_activation_payment.yaml"
    sources = {
        "readiness_manifest": {"path": str(MANIFEST.relative_to(ROOT)), "sha256": file_hash(MANIFEST)},
        "runner": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": file_hash(Path(__file__))},
        "template": {"path": str(task_source.relative_to(ROOT)), "sha256": file_hash(task_source)},
    }
    lock = {
        "phase": 13,
        "identity": OUT.name,
        "contracts": contracts,
        "task_seeds": SEEDS,
        "arms": [{"name": arm, "provider": provider, "model": model, "digest": digest}
                 for arm, provider, model, digest in ARMS],
        "sampling": {"temperature": 0.3, "top_p": 0.9, "max_tokens": 2048},
        "provider_timeout_seconds": PROVIDER_TIMEOUT,
        "arm_cap_seconds": CAP_SECONDS,
        "initial_candidates_per_baseline_arm": 6,
        "max_visible_feedback_retries": 2,
        "prompt_change_after_results": "prohibited",
        "source_hashes": sources,
    }
    for name in ("treatment-lock.json", "source-hashes.json"):
        path = OUT / name
        content = lock if name == "treatment-lock.json" else sources
        if path.exists():
            prior = json.loads(path.read_text(encoding="utf-8"))
            if prior != content:
                raise SystemExit(f"pre-call {name} does not match the locked experiment")
        else:
            path.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def observed_digests() -> dict[str, str]:
    with urlopen("http://localhost:11434/api/tags", timeout=15) as response:  # nosec B310 local Ollama
        return {str(row["name"]): str(row["digest"]) for row in json.load(response)["models"]}


def paused_sanity() -> dict[str, Any]:
    targets = {"sql.funnel.logistics_parcel_delivery", "sql.funnel.saas_activation_payment", "sql.funnel.support_resolution_chain"}
    path = ROOT / "runs" / "premium-qualification-080" / "verification" / "verification.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    selected = [row for row in rows if row["task_id"].rsplit(".v", 1)[0] in targets]
    return {"mode": "read_only", "source": str(path.relative_to(ROOT)), "records": len(selected),
            "by_contract": {key: sum(row["task_id"].rsplit(".v", 1)[0] == key for row in selected) for key in sorted(targets)}}


def feedback_envelope(base: dict[str, Any]) -> str | None:
    candidate, execution, verification = base.get("candidate"), base.get("execution"), base.get("verification")
    if not candidate or not execution or not verification:
        return None
    code = verification.get("failure_code")
    if code == "RESULT_MISMATCH":
        comparison = verification.get("comparison") or {}
        visible = {"expected_columns": comparison.get("expected_columns", []), "actual_columns": comparison.get("actual_columns", []), "differences": comparison.get("differences", [])[:20]}
        difference, diagnostic = json.dumps(visible, sort_keys=True)[:8192], "NONE"
    elif code == "EXECUTION_FAILED":
        difference = "NONE"
        diagnostic = str((execution.get("failure") or {}).get("message", "NONE"))
    else:
        return None
    envelope = f"Previous candidate SQL:\n{candidate.get('candidate_sql') or ''}\n\nVerifier outcome: {code}\nExecution diagnostic: {diagnostic}\nVisible result difference: {difference}\n\nReturn replacement DuckDB SQL only. Preserve the supplied task contract."
    forbidden = ("INDEPENDENT_ADVERSARIAL", "hidden fixtures", "mutation", "metamorphic", "oracle_version", "strategy")
    if any(value.lower() in envelope.lower() for value in forbidden):
        raise RuntimeError("feedback boundary audit failed")
    return envelope


def is_pass(row: dict[str, Any]) -> bool:
    return row.get("verification", {}).get("verdict") == "PASS"


def infrastructure_error(row: dict[str, Any]) -> bool:
    """Provider and recording failures stop an arm; SQL failures do not."""
    return "error" in row


def call(out: Path, arm: str, provider: Any, task: Any, contract: str, index: int, retry: int,
         prompt: str, feedback_assisted: bool, executor: SandboxExecutor, backend: DerivedTaskBackend) -> dict[str, Any]:
    started = time.monotonic()
    config = GenerationConfig(temperature=0.3, top_p=0.9, max_tokens=2048, seed=seed(arm, contract, index, retry))
    try:
        response = provider.generate(prompt, config)
        parsed = extract_candidate_sql(response.raw_text)
        candidate = CandidateSolution(candidate_id=build_candidate_id(task.task_id, provider.model_id, response.model_revision, "sql-v2", config, index + retry * 100), task_id=task.task_id, model=provider.model_id, model_revision=response.model_revision, prompt_version="sql-v2", generation_schema_version="1.0", provider=provider.provider_name, endpoint_id=provider.endpoint_id(), candidate_index=index + retry * 100, raw_response=response.raw_text, candidate_sql=parsed.sql, generation_config=config, generation_timestamp=stamp(), generation_duration_ms=response.generation_time_ms, finish_reason=response.finish_reason, token_usage=response.token_usage, provider_metadata={**response.provider_metadata, "feedback_assisted": feedback_assisted}, generation_status="success", parse_status=parsed.status, failure_reason=parsed.failure_reason)
        execution = executor.execute(task, candidate)
        verification = verify_candidate(task, candidate, execution, backend=backend)
        row = {"arm": arm, "contract_id": contract, "retry_index": retry, "feedback_assisted": feedback_assisted, "sampling_seed": config.seed, "candidate": candidate.model_dump(mode="json"), "execution": execution.model_dump(mode="json"), "verification": verification.model_dump(mode="json")}
    except (GenerationError, SandboxError, VerificationError) as exc:
        row = {"arm": arm, "contract_id": contract, "candidate_index": index, "retry_index": retry, "feedback_assisted": feedback_assisted, "sampling_seed": config.seed, "error": f"{type(exc).__name__}: {exc}"}
    row["wall_clock_ms"] = int((time.monotonic() - started) * 1000)
    append(out / "calls.jsonl", row)
    return row


def summary(rows: list[dict[str, Any]], contracts: list[str]) -> dict[str, Any]:
    initial = [row for row in rows if not row["feedback_assisted"]]
    contract_passes = {contract: any(is_pass(row) for row in rows if row["contract_id"] == contract) for contract in contracts}
    return {"calls": len(rows), "initial_calls": len(initial), "retry_calls": len(rows) - len(initial), "verified_pass_calls": sum(is_pass(row) for row in rows), "initial_verified_pass_rate": sum(is_pass(row) for row in initial) / max(1, len(initial)), "any_verified_pass_contracts": sum(contract_passes.values()), "any_verified_pass_rate": sum(contract_passes.values()) / len(contracts), "contracts": contract_passes}


def skipped_counts(baseline: list[dict[str, Any]], feedback: list[dict[str, Any]]) -> dict[str, int]:
    eligible = [row for row in baseline if feedback_envelope(row)]
    # Retry candidates have an offset identity; compare them to their baseline slot.
    retried = {
        (row["contract_id"], int(row.get("candidate", {}).get("candidate_index", -100)) % 100)
        for row in feedback
    }
    initial_passes = sum(is_pass(row) for row in baseline)
    hidden_or_nonvisible = sum(
        not is_pass(row) and not feedback_envelope(row) and "error" not in row for row in baseline
    )
    retry_passes = sum(is_pass(row) for row in feedback)
    return {
        "initial_pass_no_retry": initial_passes,
        "hidden_or_nonvisible_no_retry": hidden_or_nonvisible,
        "eligible_initial_failures": len(eligible),
        "eligible_failures_without_retry": sum(
            (row["contract_id"], row.get("candidate", {}).get("candidate_index")) not in retried for row in eligible
        ),
        "retry_pass_no_second_retry": retry_passes,
    }


def main() -> None:
    global OUT
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--identity",
        default=OUT.name,
        help="new scratch experiment directory name; an existing identity must match its complete pre-call lock",
    )
    parser.add_argument(
        "--lock-only",
        action="store_true",
        help="write and verify immutable pre-call artifacts without making provider calls",
    )
    args = parser.parse_args()
    if Path(args.identity).name != args.identity:
        raise SystemExit("--identity must be a directory name, not a path")
    OUT = ROOT / "scratch" / "funnel-generation-experiment" / args.identity
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    contracts = sorted(row["contract_id"] for row in manifest["contracts"] if row["family"] == "funnel" and row["status"] == "FULLY_VERIFIED")
    if contracts != sorted(SEEDS) or len(contracts) != 1:
        raise SystemExit("readiness manifest does not match the locked population")
    OUT.mkdir(parents=True, exist_ok=True)
    pre_call_lock(contracts)
    manifest_path = OUT / "manifest.json"
    if manifest_path.exists():
        prior = json.loads(manifest_path.read_text(encoding="utf-8"))
        if prior.get("contracts") != contracts or prior.get("task_seeds") != SEEDS or prior.get("arms") != [list(arm) for arm in ARMS]:
            raise SystemExit("scratch identity does not match the locked experiment")
    else:
        manifest_path.write_text(json.dumps({"phase": 13, "identity": OUT.name, "created_at": stamp(), "contracts": contracts, "task_seeds": SEEDS, "arms": ARMS, "provider_timeout_seconds": PROVIDER_TIMEOUT, "arm_cap_seconds": CAP_SECONDS, "paused_sanity": paused_sanity()}, indent=2) + "\n", encoding="utf-8")
    if args.lock_only:
        print(OUT / "treatment-lock.json")
        return
    registry, tasks = load_builtin_registry(), {}
    for contract in contracts:
        task = generate_task(registry.get(contract), SEEDS[contract])
        validate_task(task)
        tasks[contract] = task
        if not (OUT / "tasks.jsonl").exists():
            append(OUT / "tasks.jsonl", task.model_dump(mode="json"))
    sandbox = load_sandbox_config(ROOT / "configs" / "sandbox_production.yaml")
    executor, backend = SandboxExecutor(sandbox), DerivedTaskBackend(sandbox)
    existing = load_rows(OUT)
    baselines, summaries, stopped = {}, {}, {}
    for arm, provider_name, model, expected_digest in ARMS:
        prior_rows = [row for row in existing if row["arm"] == arm]
        if arm in stopped:
            continue
        observed = observed_digests()
        if observed.get(model) != expected_digest:
            stopped[arm] = "model digest mismatch"
            continue
        paired = arm.replace("-feedback", "-baseline")
        if arm.endswith("-feedback") and paired not in baselines:
            stopped[arm] = "paired baseline unavailable"
            continue
        provider = create_provider(provider_name, base_url="http://localhost:11434/v1", model_id=model, model_revision="ollama-digest:" + expected_digest, timeout_s=PROVIDER_TIMEOUT, max_retries=0)
        # A resumed scratch identity retains the time already charged to this
        # arm; a restart must not create a fresh three-hour allowance.
        started = time.monotonic() - sum(row.get("wall_clock_ms", 0) for row in prior_rows) / 1000
        rows = prior_rows
        if arm.endswith("-baseline"):
            for contract in contracts:
                for index in range(6):
                    if any(row["contract_id"] == contract and row.get("candidate", {}).get("candidate_index") == index for row in rows):
                        continue
                    if time.monotonic() - started >= CAP_SECONDS:
                        stopped[arm] = "three-hour arm cap"
                        break
                    row = call(OUT, arm, provider, tasks[contract], contract, index, 0, build_sql_prompt(tasks[contract]), False, executor, backend)
                    rows.append(row)
                    if infrastructure_error(row):
                        stopped[arm] = "provider timeout, interruption, or infrastructure fault"
                        break
                if arm in stopped:
                    break
            baselines[arm] = rows
        else:
            for base in baselines[paired]:
                envelope = feedback_envelope(base)
                if not envelope:
                    continue
                for retry in (1, 2):
                    index = int(base["candidate"]["candidate_index"])
                    prior_retry = next((row for row in rows if row["contract_id"] == base["contract_id"] and int(row.get("candidate", {}).get("candidate_index", -100)) % 100 == index and row["retry_index"] == retry), None)
                    if prior_retry:
                        if is_pass(prior_retry) or infrastructure_error(prior_retry):
                            break
                        continue
                    if retry == 2 and any(is_pass(row) or infrastructure_error(row) for row in rows if row["contract_id"] == base["contract_id"] and row.get("candidate", {}).get("candidate_index") == index and row["retry_index"] == 1):
                        break
                    if time.monotonic() - started >= CAP_SECONDS:
                        stopped[arm] = "three-hour arm cap"
                        break
                    row = call(OUT, arm, provider, tasks[base["contract_id"]], base["contract_id"], index, retry, build_sql_prompt(tasks[base["contract_id"]]) + "\n\n" + envelope, True, executor, backend)
                    rows.append(row)
                    if infrastructure_error(row):
                        stopped[arm] = "provider timeout, interruption, or infrastructure fault"
                        break
                if arm in stopped:
                    break
        combined = baselines[paired] + rows if arm.endswith("-feedback") else baselines[arm]
        summaries[arm] = summary(combined, contracts)
        if arm.endswith("-feedback"):
            summaries[arm]["skipped"] = skipped_counts(baselines[paired], rows)
    report = {"identity": OUT.name, "phase": 13, "finished_at": stamp(), "expected": {"contracts": len(contracts), "initial_candidates_per_baseline_arm": 6, "feedback_retry_limit_per_eligible_initial_failure": 2}, "summaries": summaries, "stopped": stopped, "directional": {"qwen_minus_pinned_initial": summaries.get("qwen-baseline", {}).get("initial_verified_pass_rate", 0) - summaries.get("pinned-baseline", {}).get("initial_verified_pass_rate", 0), "qwen_minus_pinned_any": summaries.get("qwen-feedback", summaries.get("qwen-baseline", {})).get("any_verified_pass_rate", 0) - summaries.get("pinned-feedback", summaries.get("pinned-baseline", {})).get("any_verified_pass_rate", 0)}}
    (OUT / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    checklist = {
        "pre_call_lock": (OUT / "treatment-lock.json").exists() and (OUT / "source-hashes.json").exists(),
        "population_is_fully_verified_funnel_only": contracts == ["sql.funnel.saas_activation_payment"],
        "arms_in_authorized_order": list(summaries) == [arm[0] for arm in ARMS],
        "initial_cap_per_baseline_arm": all(summary["initial_calls"] == 6 for arm, summary in summaries.items() if arm.endswith("baseline")),
        "feedback_retry_cap": all(summary["retry_calls"] <= 12 for arm, summary in summaries.items() if arm.endswith("feedback")),
        "no_arm_stopped": not stopped,
        "prompt_lock_retained": True,
    }
    status = {
        "phase": 13,
        "result": "PASS" if all(checklist.values()) else "FAIL",
        "calls": sum(item["calls"] for item in summaries.values()),
        "checklist": checklist,
        "stopped": stopped,
    }
    (OUT / "checklist.json").write_text(json.dumps(checklist, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUT / "report.json")


if __name__ == "__main__":
    main()
