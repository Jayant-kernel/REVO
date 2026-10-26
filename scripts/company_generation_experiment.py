"""Bounded INTERNAL_ONLY subset experiment using the factory's public execution APIs."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from scripts.engineering_campaign import ROOT, safety
from scripts.engineering_pipeline import append
from verified_data_factory.generation import (
    GenerationConfig,
    GenerationResponse,
    TokenUsage,
    build_sql_prompt,
    extract_candidate_sql,
    generate_candidate,
)
from verified_data_factory.generation.errors import PermanentProviderError
from verified_data_factory.generation.providers.qwen import QwenProvider
from verified_data_factory.local_lock import exclusive_lock
from verified_data_factory.production import load_config as load_production_config
from verified_data_factory.production.api import preflight
from verified_data_factory.quality import analyze_dataset, export_dataset, load_quality_config
from verified_data_factory.quality.models import VerifiedRecord
from verified_data_factory.sandbox import SandboxExecutor, load_config
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification import verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.readiness import authoritative_records, qualify
from verified_data_factory.verification.receipt_validation import (
    digest,
    required_sources,
    runtime_identity,
)

MODEL = "qwen3:8b"
MODEL_DIGEST = "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"
LICENSE_DIGEST = "d18a5cc71b84bc4af394a31116bd3932b42241de70c77d2b76d69a314ec8aa12"
ENDPOINT = "http://127.0.0.1:11434/v1"
RIGHTS = "governance/internal-generation-qwen3-8b-20261010.json"
BUDGET = ROOT / "scratch/funnel_experiment/engineering/generation-budget-events.jsonl"
TASKS = (("sql.aggregation.fulfillment_sla_dashboard", 1),
         ("sql.aggregation.manufacturing_line_scrap", 1), ("sql.joins.saas_paid_invoices", 1))
MAX_ATTEMPTS, MAX_SECONDS, CALL_TIMEOUT = 360, 14400, 180


def write_new(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, default=str)
        handle.flush()
        os.fsync(handle.fileno())


def budget_usage(events: list[dict[str, Any]]) -> dict[str, Any]:
    starts, finishes = {}, {}
    for event in events:
        identifier = event["attempt_id"]
        if event["state"] == "started":
            if identifier in starts:
                raise ValueError("duplicate physical-call reservation")
            seconds = event["reserved_seconds"]
            if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
                raise ValueError("invalid generation time reservation")
            starts[identifier] = event
        elif event["state"] == "finished":
            seconds = event["elapsed_seconds"]
            if (identifier not in starts or identifier in finishes or isinstance(seconds, bool)
                    or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0):
                raise ValueError("invalid generation finish accounting")
            finishes[identifier] = event
        else:
            raise ValueError("unknown generation accounting state")
    return {"physical_attempts": len(starts),
            "generation_seconds": sum(finishes[key]["elapsed_seconds"] if key in finishes else value["reserved_seconds"]
                                      for key, value in starts.items()),
            "unfinished_attempts": sorted(starts.keys()-finishes.keys())}


def reserve(events: list[dict[str, Any]], identifier: str) -> dict[str, Any]:
    usage = budget_usage(events)
    if any(event["attempt_id"] == identifier for event in events):
        raise ValueError("physical call identity already spent; no re-call")
    if (usage["unfinished_attempts"] or usage["physical_attempts"] >= MAX_ATTEMPTS
            or usage["generation_seconds"] + CALL_TIMEOUT > MAX_SECONDS):
        raise ValueError("cumulative generation budget exhausted or interrupted call unresolved")
    return {"attempt_id": identifier, "state": "started", "reserved_seconds": CALL_TIMEOUT,
            "started_at": datetime.now(UTC).isoformat(), "model": MODEL, "model_digest": MODEL_DIGEST}


def source_hashes() -> dict[str, str]:
    result = required_sources()
    for folder in ("scripts", "tests"):
        result.update({path.relative_to(ROOT).as_posix(): digest(path) for path in (ROOT / folder).rglob("*.py")})
    for name in (RIGHTS, "pyproject.toml", "configs/sandbox_production.yaml", "configs/quality_premium_93.yaml"):
        result[name] = digest(ROOT / name)
    return result


class RecordedQwen(QwenProvider):
    """No retry/fallback; exact model-visible prompt and raw HTTP response retained."""

    def __init__(self, client: httpx.Client, run: Path, *, cpu: bool = False) -> None:
        super().__init__(ENDPOINT, model_id=MODEL, model_revision="ollama-manifest:"+MODEL_DIGEST,
                         timeout_s=CALL_TIMEOUT, max_retries=0, client=client)
        self.run = run
        self.slot = 0
        self.cpu = cpu

    def endpoint_id(self) -> str:
        if not self.cpu:
            return super().endpoint_id()
        return "qwen:"+hashlib.sha256(f"qwen|{MODEL}|http://127.0.0.1:11434/api/chat".encode()).hexdigest()[:12]

    def _payload(self, prompt: str, config: GenerationConfig) -> dict[str, Any]:
        # Official Qwen soft non-thinking directive; no task answers or hidden data.
        return super()._payload(prompt+"\n/no_think", config)

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        events = [json.loads(line) for line in BUDGET.read_text().splitlines()] if BUDGET.exists() else []
        identifier = f"{self.run.name}:{self.slot}"
        started = reserve(events, identifier)
        directory = self.run / f"attempt-{self.slot:03d}"
        current = self._client.get("http://127.0.0.1:11434/api/tags").json() if self._client is not None else {}
        if not any(item.get("name") == MODEL and item.get("digest") == MODEL_DIGEST for item in current.get("models", [])):
            raise ValueError("installed model identity changed before physical call")
        url = ENDPOINT+"/chat/completions"
        body = payload
        if self.cpu:
            url = "http://127.0.0.1:11434/api/chat"
            body = {"model": payload["model"], "messages": payload["messages"], "stream": False,
                    "think": False, "options": {"num_gpu": 0, "num_ctx": 4096,
                    "num_predict": payload["max_tokens"], "temperature": payload["temperature"],
                    "top_p": payload["top_p"], "seed": payload["seed"]}}
        write_new(directory / "request.json", {"url": url, "body": body})
        started.update(request_sha256=digest(directory / "request.json"), actual_endpoint=url)
        append(BUDGET, started)
        began = time.monotonic()
        response_observed = False
        try:
            response = self._client.post(url, json=body) if self.cpu and self._client is not None else super()._post(payload)
            response_observed = True
            write_new(directory / "http-response.json", {"status_code": response.status_code,
                                                          "body": response.text})
            return response
        finally:
            if response_observed:
                append(BUDGET, {"attempt_id": identifier, "state": "finished",
                                "elapsed_seconds": time.monotonic()-began,
                                "response_sha256": digest(directory / "http-response.json")})
            else:
                # Unknown server outcome remains reserved and blocks the next call.
                write_new(directory / "indeterminate-call.json", {
                    "attempt_id": identifier, "elapsed_seconds_observed": time.monotonic()-began,
                    "status": "SERVER_OUTCOME_UNKNOWN_NO_RECALL", "reserved_seconds": CALL_TIMEOUT})

    def _parse_response(self, response: httpx.Response, elapsed_ms: int) -> Any:
        if self.cpu:
            try:
                data = response.json()
            except ValueError as exc:
                raise PermanentProviderError("native model response is not JSON") from exc
            if not isinstance(data, dict):
                raise PermanentProviderError("native model response is not an object")
            content = data.get("message", {}).get("content")
            if not isinstance(content, str) or data.get("model") != MODEL:
                raise PermanentProviderError("native model response identity/content missing")
            usage = None
            if "prompt_eval_count" in data and "eval_count" in data:
                usage = TokenUsage(prompt_tokens=data["prompt_eval_count"], completion_tokens=data["eval_count"],
                                   total_tokens=data["prompt_eval_count"]+data["eval_count"])
            result = GenerationResponse(raw_text=content, model=MODEL, model_revision=self._model_revision,
                finish_reason=data.get("done_reason", "unknown"), token_usage=usage, generation_time_ms=elapsed_ms,
                provider_metadata={"base_url": "http://127.0.0.1:11434", "actual_endpoint": "/api/chat",
                                   "num_gpu": 0, "num_ctx": 4096, "think": False})
        else:
            result = super()._parse_response(response, elapsed_ms)
        return result.model_copy(update={"provider_metadata": {
            **result.provider_metadata, "origin": "LOCAL_MODEL_OUTPUT",
            "prompt_adapter_version": "qwen-no-think-soft-v1", "prompt_suffix": "/no_think",
            "physical_transport_retries": 0,
        }})


def freeze(destination: Path, *, cpu: bool = False,
           tasks: tuple[tuple[str, int], ...] = TASKS, candidates_per_task: int = 2) -> None:
    if not tasks or len(set(tasks)) != len(tasks) or type(candidates_per_task) is not int or not 1 <= candidates_per_task <= 3:
        raise ValueError("declare distinct tasks and one to three candidates per task")
    if len(tasks) * candidates_per_task > 60:
        raise ValueError("planned calls exceed the bounded batch cap")
    if not destination.resolve().is_relative_to((ROOT / "runs").resolve()):
        raise ValueError("experiment must use a new local runs directory")
    destination.mkdir(exist_ok=False)
    rights = json.loads((ROOT / RIGHTS).read_text())
    if (rights["model"] != MODEL or rights["ollama_manifest_digest"] != MODEL_DIGEST
            or rights["internal_generation"] != "PERMITTED_BY_OBSERVED_LICENSE_AND_USER_EXPERIMENT_SCOPE"):
        raise ValueError("internal-use evidence does not authorize this exact artifact")
    manifest = Path.home() / ".ollama/models/manifests/registry.ollama.ai/library/qwen3/8b"
    license_blob = Path.home() / (".ollama/models/blobs/sha256-"+LICENSE_DIGEST)
    if digest(manifest) != MODEL_DIGEST or digest(license_blob) != LICENSE_DIGEST:
        raise ValueError("installed model/license identity changed")
    registered = {(row["contract_id"], row["contract_version"]): row for row in authoritative_records(ROOT)}
    task_instances = []
    for index, pair in enumerate(tasks):
        admission = qualify(ROOT, registered[pair])
        if not admission["eligible"]:
            raise ValueError(f"task qualification unavailable: {pair}: {admission}")
        task_instances.append(generate_task(load_builtin_registry().get(*pair), 101010+index))
    write_new(destination / "protocol.json", {
        "schema_version": 2, "scope": "INTERNAL_ONLY_PARTIAL_EXPERIMENT", "human_review": "PENDING",
        "model": MODEL, "model_digest": MODEL_DIGEST, "provider": "qwen", "endpoint": ENDPOINT,
        "generation_transport": "native_ollama_cpu" if cpu else "openai_compatible_gpu",
        "actual_generation_endpoint": "http://127.0.0.1:11434/api/chat" if cpu else ENDPOINT+"/chat/completions",
        "requested_num_gpu": 0 if cpu else "server_default",
        "rights_record": {"path": RIGHTS, "sha256": digest(ROOT / RIGHTS)}, "external_sharing": "BLOCKED",
        "tasks": [task.model_dump(mode="json", by_alias=True) for task in task_instances],
        "candidates_per_task": candidates_per_task, "planned_calls": len(tasks) * candidates_per_task, "batch_cap": 60,
        "sampling": {"temperature": 0.7, "top_p": 0.8, "max_tokens": 2048},
        "prompt_adapter_version": "qwen-no-think-soft-v1", "transport_retries": 0,
        "call_timeout_seconds": CALL_TIMEOUT, "cumulative_attempt_cap": MAX_ATTEMPTS,
        "cumulative_generation_seconds_cap": MAX_SECONDS, "budget_journal": BUDGET.relative_to(ROOT).as_posix(),
        "stop_rules": ["first provider/transport failure", "any infrastructure/oracle fault",
                       "two same-task candidates without STRONG admission", "source/model drift or exhausted budget"],
        "runtime": runtime_identity(), "source_hashes": source_hashes(),
        "hardware": {"platform": platform.platform(), "processor": platform.processor(),
                     "gpu": subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                                                      "--format=csv,noheader"], text=True).strip()},
    })
    write_new(destination / "protocol-binding.json", {"sha256": digest(destination / "protocol.json")})


def validate_attempt_binding(run: Path, slot: int, candidate: Any, events: list[dict[str, Any]]) -> None:
    identifier = f"{run.name}:{slot}"
    matching = [event for event in events if event["attempt_id"] == identifier]
    starts = [event for event in matching if event["state"] == "started"]
    finishes = [event for event in matching if event["state"] == "finished"]
    directory = run / f"attempt-{slot:03d}"
    if (len(starts) != 1 or len(finishes) != 1 or not starts[0].get("request_sha256")
            or not finishes[0].get("response_sha256")):
        raise ValueError("unbound or interrupted legacy generation cannot establish current provenance")
    if (digest(directory / "request.json") != starts[0]["request_sha256"]
            or digest(directory / "http-response.json") != finishes[0]["response_sha256"]):
        raise ValueError("physical generation request/response changed")
    request = json.loads((directory / "request.json").read_text())
    response = json.loads((directory / "http-response.json").read_text())
    raw = json.loads(response["body"])
    content = raw.get("message", {}).get("content") if request["url"].endswith("/api/chat") else raw["choices"][0]["message"]["content"]
    if (request["url"] != starts[0]["actual_endpoint"] or request["body"]["model"] != candidate.model
            or content != candidate.raw_response or candidate.model_revision != "ollama-manifest:"+starts[0]["model_digest"]):
        raise ValueError("candidate differs from bound physical model output")
    if candidate.candidate_sql != extract_candidate_sql(content).sql:
        raise ValueError("candidate SQL substituted independently of physical model output")


def execute(destination: Path) -> None:
    from verified_data_factory.task_engine.models import TaskInstance

    protocol = json.loads((destination / "protocol.json").read_text())
    if protocol.get("schema_version") != 2:
        raise ValueError("older experimental producer lacks physical-content bindings; preserve history, use a new run")
    if json.loads((destination / "protocol-binding.json").read_text())["sha256"] != digest(destination / "protocol.json"):
        raise ValueError("experiment protocol modified after freeze")
    if protocol["source_hashes"] != source_hashes() or protocol["runtime"] != runtime_identity():
        raise ValueError("frozen experiment source/runtime drift")
    # Preflight is read-only; the full-production scheduler is never invoked.
    config = load_production_config(ROOT / "configs/production/premium_qualification_80.yaml")
    model = config.model.model_copy(update={"model_id": MODEL, "model_revision": "ollama-manifest:"+MODEL_DIGEST,
                                          "provider": "qwen", "endpoint": ENDPOINT})
    observed = preflight(config.model_copy(update={"model": model}))
    write_new(destination / "preflight.json", observed)
    if not observed["ok"]:
        raise ValueError("shared production preflight failed; no inference performed")
    rows, verified = [], []
    reason = "planned subset completed"
    with exclusive_lock(BUDGET.with_suffix(".lock")), httpx.Client(timeout=CALL_TIMEOUT, trust_env=False) as client:
        provider = RecordedQwen(client, destination, cpu=protocol["generation_transport"] == "native_ollama_cpu")
        sandbox_config = load_config(ROOT / "configs/sandbox_production.yaml")
        executor, backend = SandboxExecutor(sandbox_config), DerivedTaskBackend(sandbox_config)
        for task_data in protocol["tasks"]:
            task = TaskInstance.model_validate(task_data)
            task_strong = 0
            for index in range(protocol["candidates_per_task"]):
                provider.slot = len(rows)
                directory = destination / f"attempt-{provider.slot:03d}"
                directory.mkdir(exist_ok=False)
                write_new(directory / "public-prompt.json", {"base_prompt": build_sql_prompt(task),
                                                              "model_visible_suffix": "/no_think"})
                sampling = GenerationConfig(**protocol["sampling"], seed=20261010+provider.slot)
                result = generate_candidate(task, provider, sampling, index)
                write_new(directory / "generation.json", result.model_dump(mode="json"))
                row: dict[str, Any] = {"task_id": task.task_id, "family": task.family,
                    "generation_status": result.generation_status,
                    "origin": "LOCAL_MODEL_OUTPUT" if result.candidate_solution is not None else "LOCAL_PROVIDER_ATTEMPT_NO_OUTPUT",
                    "verdict": "NOT_EXECUTED", "strength": "UNKNOWN", "partial_strong": False}
                if result.candidate_solution is None:
                    rows.append(row)
                    reason = "provider failed; stop before another physical call"
                    break
                candidate = result.candidate_solution
                events = [json.loads(line) for line in BUDGET.read_text().splitlines()]
                validate_attempt_binding(destination, provider.slot, candidate, events)
                execution = executor.execute(task, candidate)
                write_new(directory / "execution.json", execution.model_dump(mode="json"))
                verification = verify_candidate(task, candidate, execution, backend=backend)
                write_new(directory / "verification.json", verification.model_dump(mode="json"))
                strong = (verification.verdict == "PASS" and verification.verification_strength == "STRONG"
                          and verification.mutation is not None and verification.mutation.mutation_score == 1.0)
                row.update(candidate_id=candidate.candidate_id, verdict=verification.verdict,
                           strength=verification.verification_strength, partial_strong=strong,
                           generation_content_binding="PASS")
                rows.append(row)
                task_strong += int(strong)
                verified.append(VerifiedRecord(task=task, candidate=candidate, execution=execution, verification=verification))
                write_new(directory / "case-result.json", row)
                print(json.dumps(row), flush=True)
                if execution.status in {"SANDBOX_ERROR", "TIMEOUT"} or (verification.oracle is not None and not verification.oracle.ok):
                    reason = "infrastructure/oracle defect; stop generation"
                    break
                if index >= 1 and not task_strong:
                    reason = "two same-task candidates lack STRONG admission; stop before another physical call"
                    break
            if reason != "planned subset completed":
                break
            if not task_strong:
                reason = "same-task outputs lack STRONG admission; investigate before further generation"
                break
        if verified:
            quality_config = load_quality_config(ROOT / "configs/quality_premium_93.yaml").model_copy(update={"audit_rate": 0.0})
            analysis = analyze_dataset(verified, quality_config)
            export_dataset(analysis.qualities, {record.candidate.candidate_id: record for record in verified},
                           analysis.health.model_dump(mode="json"), [], destination / "quality/export")
        events = [json.loads(line) for line in BUDGET.read_text().splitlines()] if BUDGET.exists() else []
        write_new(destination / "report.json", {"scope": "PARTIAL_INTERNAL_EXPERIMENT_NOT_80_ROW_ACCEPTANCE",
            "status": "COMPLETE" if reason == "planned subset completed" else "PAUSED", "reason": reason,
            "rows": rows, "budget_used_cumulative": budget_usage(events), "paid_cost": 0,
            "local_monetary_compute_cost": "NOT_MEASURED", "accepted_full_candidate_records": 0,
            "human_review": "PENDING", "external_sharing": "BLOCKED",
            "live_model_runtime": client.get("http://127.0.0.1:11434/api/ps").json()})
        print(json.dumps({"status": "COMPLETE" if reason == "planned subset completed" else "PAUSED",
                          "reason": reason, "budget_used_cumulative": budget_usage(events),
                          "accepted_full_candidate_records": 0, "report": str(destination / "report.json")}), flush=True)
    if protocol["source_hashes"] != source_hashes():
        raise ValueError("source changed during experiment; outcomes remain retained but uncertified")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--cpu", action="store_true", help="Freeze a native Ollama num_gpu=0 experiment after recorded GPU failure")
    args = parser.parse_args()
    if args.freeze == args.execute:
        parser.error("choose exactly --freeze or --execute")
    if args.cpu and not args.freeze:
        parser.error("CPU setting must be frozen, not changed at execution")
    safety()
    try:
        freeze(args.run.resolve(), cpu=args.cpu) if args.freeze else execute(args.run.resolve())
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Experiment refused: {exc}. Preserve existing evidence and use an unused run identity.\n")


if __name__ == "__main__":
    main()
