"""One durable orchestration path for injected stub or local model providers."""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Any, ClassVar, Protocol
from urllib.request import Request, urlopen

from verified_data_factory.generation import (
    CandidateSolution,
    GenerationConfig,
    build_sql_prompt,
    extract_candidate_sql,
)
from verified_data_factory.local_lock import exclusive_lock
from verified_data_factory.sandbox import SandboxExecutor, load_config
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification import verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend


class Provider(Protocol):
    def generate(self, prompt: str, seed: int) -> str: ...
    def metadata(self) -> dict[str, Any]: ...
    def unload(self) -> None: ...


class IndeterminateCall(RuntimeError):
    """Provider execution cannot be reconstructed; never silently re-call."""


class LocalOllama:
    """Opt-in provider adapter. Construction never pulls models or generates."""
    ALLOWED: ClassVar[dict[str, str]] = {
        "alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest": "a2d26ea0b96b7a40afd673158d5cf44de25eff07fc8abf835e2cde5444632bc4",
        "mdq100/Qwen3-Coder-30B-A3B-Instruct:30b": "88cc37b8585d9ce9df3193b9624a7792c1fd9177c397e90c675b9370349aaad5",
    }
    def __init__(self, model: str, *, timeout: float = 180, context_size: int = 16384) -> None:
        if model not in self.ALLOWED or timeout <= 0 or context_size < 1:
            raise ValueError("model or runtime settings not authorized")
        self.model, self.timeout, self.context_size = model, timeout, context_size
        self._observed: dict[str, Any] | None = None

    def request(self, path: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode()
        req = Request("http://localhost:11434" + path, data=body, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=self.timeout) as response:  # nosec B310: explicit local-only endpoint.
            result = json.load(response)
        if not isinstance(result, dict):
            raise TypeError("local provider response is not an object")
        return result

    def metadata(self) -> dict[str, Any]:
        if self._observed is None:
            tags = self.request("/api/tags", None)
            item = next((m for m in tags.get("models", []) if m.get("name") == self.model), None)
            if item is None or item.get("digest") != self.ALLOWED[self.model]:
                raise ValueError("local model missing or digest changed; no download or fallback")
            show = self.request("/api/show", {"model": self.model})
            self._observed = {"name": self.model, "digest": item["digest"],
                              "quantization": show.get("details", {}).get("quantization_level", "UNAVAILABLE"),
                              "context_size": self.context_size, "thinking": False,
                              "temperature": 0.3, "top_p": 0.9, "timeout_seconds": self.timeout}
        return dict(self._observed)

    def generate(self, prompt: str, seed: int) -> str:
        self.metadata()
        result = self.request("/api/generate", {"model": self.model, "prompt": prompt, "stream": False,
            "think": False, "options": {"seed": seed, "temperature": 0.3, "top_p": 0.9,
                                         "num_ctx": self.context_size, "num_predict": 2048}})
        if not isinstance(result.get("response"), str):
            raise TypeError("model response missing text")
        return str(result["response"])

    def unload(self) -> None:
        self.request("/api/generate", {"model": self.model, "keep_alive": 0})


def append(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def lock(root: Path, protocol: dict[str, Any], sources: dict[str, str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    payload = {"protocol": protocol, "sources": sources}
    path = root / "protocol.json"
    if path.exists():
        if json.loads(path.read_text()) != payload:
            raise ValueError("protocol or sources changed")
    else:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())


def execute_sql(task: Any, sql: str, seed: int) -> dict[str, Any]:
    """Reuse the production executor and verifier, never a parallel evaluator."""
    parsed = extract_candidate_sql(sql)
    candidate = CandidateSolution(candidate_id=f"{task.task_id}.engineering-{seed}-{hashlib.sha256(sql.encode()).hexdigest()[:12]}",
        task_id=task.task_id, model="injected-provider", model_revision="locked", prompt_version="sql-v2",
        generation_schema_version="1.0", provider="injected-provider", endpoint_id="locked-local",
        candidate_index=0, raw_response=sql, candidate_sql=parsed.sql,
        generation_config=GenerationConfig(seed=seed, temperature=0.3, top_p=0.9),
        generation_timestamp="2026-10-07T00:00:00+00:00", generation_duration_ms=0,
        parse_status=parsed.status, failure_reason=parsed.failure_reason)
    config = load_config(Path(__file__).resolve().parents[1] / "configs/sandbox_production.yaml")
    observed = SandboxExecutor(config).execute(task, candidate)
    verdict = verify_candidate(task, candidate, observed, backend=DerivedTaskBackend(config))
    return {"execution": observed.model_dump(mode="json"), "verification": verdict.model_dump(mode="json")}


def runtime_uncertain(result: dict[str, Any]) -> bool:
    if result.get("execution", {}).get("status") in {"TIMEOUT", "SANDBOX_ERROR"}:
        return True
    verification = result.get("verification", {})
    cases = (verification.get("hidden") or {}).get("cases", [])
    # A witnessed wrong answer remains a failure even if another case timed out.
    failures = [c for c in cases if c.get("status") == "FAIL"]
    timed = [c for c in cases if c.get("detail") == "hidden execution TIMEOUT"]
    if timed and all(c.get("detail") == "hidden execution TIMEOUT" for c in failures):
        return True
    return bool(verification.get("verdict") == "INCONCLUSIVE" and verification.get("failure_code") == "SANDBOX_INFRA_ERROR")


def run_slot(root: Path, provider: Provider, key: tuple[str, str, int, int, int, int], *, cap_seconds: float = 10800,
             retry_input: dict[str, Any] | None = None, pause_after_response: bool = False,
             pause_at: str | None = None) -> dict[str, Any]:
    with exclusive_lock(root / "writer.lock"):
        return _run_slot_locked(root, provider, key, cap_seconds=cap_seconds,
                                retry_input=retry_input, pause_after_response=pause_after_response,
                                pause_at=pause_at)


def _checkpoint(root: Path, name: str, selected: str | None) -> None:
    if selected == name:
        (root / (name + "-paused")).touch()
        while True:
            time.sleep(0.1)


def _run_slot_locked(root: Path, provider: Provider, key: tuple[str, str, int, int, int, int], *,
                     cap_seconds: float, retry_input: dict[str, Any] | None,
                     pause_after_response: bool, pause_at: str | None) -> dict[str, Any]:
    arm, contract, version, _index, seed, retry = key
    if any(type(value) is not int for value in (version, _index, seed, retry)):
        raise ValueError("version, candidate slot, seed and retry must be exact integers")
    if isinstance(cap_seconds, bool) or not math.isfinite(cap_seconds) or cap_seconds > 10800:
        raise ValueError("wall-clock cap exceeds the locked maximum or is not finite")
    if retry not in (0, 1, 2):
        raise ValueError("retry limit exceeded")
    if _index not in range(6) or seed < 0:
        raise ValueError("negative/out-of-range candidate slot or seed")
    allowed = {"stub-baseline": "stub", "stub-feedback": "stub",
               "pinned-baseline": "stub-pinned", "pinned-feedback": "stub-pinned",
               "qwen-baseline": "stub-qwen", "qwen-feedback": "stub-qwen"}
    observed_name = provider.metadata().get("name")
    paired_local = isinstance(provider, LocalOllama) and (
        arm in {"pinned-baseline", "pinned-feedback"} and provider.model == next(iter(LocalOllama.ALLOWED))
        or arm in {"qwen-baseline", "qwen-feedback"} and provider.model == list(LocalOllama.ALLOWED)[1]
    )
    if arm not in allowed or (observed_name != allowed[arm] and not paired_local):
        raise ValueError("unsupported arm/provider pairing")
    if (arm.endswith("-baseline") and retry != 0) or (arm.endswith("-feedback") and retry == 0):
        raise ValueError("arm and retry progression differ")
    if retry and (retry_input is None or retry_input.get("verification", {}).get("verdict") != "FAIL"):
        raise ValueError("retry requires failed baseline; success cannot be retried")
    ledger = root / "calls.jsonl"
    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line] if ledger.exists() else []
    for row in rows:
        prior_key = row.get("key", [])
        if (len(prior_key) == 6 and prior_key[:4] == list(key)[:4]
                and prior_key[-1] == retry and prior_key[4] != seed):
            raise ValueError("sampling seed changed for an existing logical slot")
    if retry:
        assert retry_input is not None
        baseline_key = retry_input.get("key", [])
        prior_arm = arm.replace("-feedback", "-baseline") if retry == 1 else arm
        if (len(baseline_key) != 6 or baseline_key[1:4] != list(key)[1:4]
                or baseline_key[-1] != retry - 1 or baseline_key[0] != prior_arm):
            raise ValueError("retry is not paired to the same baseline slot")
        if not any(r == retry_input and r["state"] == "completed" for r in rows):
            raise ValueError("retry baseline must be an exact completed ledger receipt")
    # Provider sampling seeds do not change the paired baseline task/fixture.
    task = generate_task(load_builtin_registry().get(contract, version), 1)
    public = build_sql_prompt(task)
    if retry:
        if retry_input is None:
            raise ValueError("retry requires a baseline receipt")
        verification = retry_input["verification"]
        code = verification.get("failure_code")
        if code not in {"RESULT_MISMATCH", "EXECUTION_FAILED"}:
            raise ValueError("no visible feedback available")
        # Only visible comparison diagnostics; never hidden stage evidence.
        if code == "RESULT_MISMATCH":
            comparison = verification.get("comparison") or {}
            diagnostic = {name: comparison.get(name, []) for name in ("expected_columns", "actual_columns", "differences")}
        else:
            failure = retry_input.get("execution", {}).get("failure") or {}
            diagnostic = {name: failure.get(name, "") for name in ("code", "message")}
        public += "\nVisible diagnostic: " + json.dumps(diagnostic, sort_keys=True) + "\nReturn corrected DuckDB SQL."
    workspace = Path(__file__).resolve().parents[1]
    dependencies = [Path(__file__).resolve(), workspace / "pyproject.toml", workspace / "configs/sandbox_production.yaml",
                    workspace / "scripts/engineering_four_arm_stub.py", workspace / "scripts/engineering_stub_worker.py",
                    workspace / "tests/test_business_tasks.py"]
    dependencies += [p for folder in ("src/verified_data_factory", "templates/sql")
                      for p in (workspace / folder).rglob("*") if p.is_file() and p.suffix in {".py", ".yaml"} and "__pycache__" not in p.parts]
    dependencies += [p for folder in ("scripts", "tests") for p in (workspace / folder).rglob("*.py")]
    hashes = {p.relative_to(workspace).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dependencies)}
    protocol = {"ledger_version": 2, "cap_seconds": cap_seconds, "max_retries": 2,
                "max_evaluation_attempts": 2, "temperature": 0.3, "top_p": 0.9,
                "contract": contract, "version": version, "model": provider.metadata()}
    lock(root, protocol, hashes)
    prompt_hash = hashlib.sha256(public.encode()).hexdigest()
    token = hashlib.sha256(json.dumps(key).encode()).hexdigest()
    prompt_path = root / (token + ".prompt.json")
    prompt = {"key": key, "hash": prompt_hash, "public_prompt": public}
    if prompt_path.exists():
        previous = json.loads(prompt_path.read_text())
        if previous["hash"] != prompt_hash:
            raise ValueError("actual built prompt changed")
    else:
        with prompt_path.open("x", encoding="utf-8") as handle:
            json.dump(prompt, handle)
            handle.flush()
            os.fsync(handle.fileno())
    prior = [r for r in rows if r.get("key") == list(key)]
    if retry == 2 and any(r["state"] == "completed" and r.get("key", [])[:4] == list(key)[:4]
                          and r.get("key", [])[-1:] == [1] and r.get("verification", {}).get("verdict") == "PASS" for r in rows):
        raise ValueError("matching first retry already succeeded")
    done = next((r for r in prior if r["state"] == "completed"), None)
    if done is not None:
        return dict(done)
    response = next((r for r in prior if r["state"] == "response"), None)
    if response is None and any(r["state"] == "started" for r in prior):
        raise IndeterminateCall("started provider call has no durable response; not re-called")
    starts = [r["started_at"] for r in rows if r.get("arm") == arm and r["state"] == "started"]
    if response is None and starts and time.time() - min(starts) >= cap_seconds:
        append(ledger, {"arm": arm, "key": key, "state": "stopped", "reason": "wall_clock_cap"})
        raise TimeoutError("arm wall-clock cap reached")
    if response is None:
        if cap_seconds <= 0:
            append(ledger, {"arm": arm, "key": key, "state": "stopped", "reason": "wall_clock_cap"})
            raise TimeoutError("arm wall-clock cap reached")
        append(ledger, {"arm": arm, "key": key, "state": "started", "started_at": time.time(), "prompt_hash": prompt_hash})
        output = provider.generate(public, seed)
        response = {"arm": arm, "key": key, "state": "response", "output": output, "model": provider.metadata()}
        append(ledger, response)
    if pause_after_response:
        (root / "response-paused").touch()
        while True:
            time.sleep(0.1)
    attempts = [r for r in rows if r.get("key") == list(key) and r["state"] == "evaluation_started"]
    finishes = [r for r in rows if r.get("key") == list(key) and r["state"] == "evaluation"]
    result = finishes[-1]["result"] if finishes else None
    for attempt_number in range(len(attempts), 2):
        if result is not None and not runtime_uncertain(result):
            break
        attempt_id = token + ".evaluation-" + str(attempt_number + 1)
        append(ledger, {"arm": arm, "key": key, "state": "evaluation_started",
                        "attempt": attempt_number + 1, "attempt_id": attempt_id,
                        "sql_sha256": hashlib.sha256(response["output"].encode()).hexdigest()})
        _checkpoint(root, "evaluation-start", pause_at)
        result = execute_sql(task, response["output"], seed)
        append(ledger, {"arm": arm, "key": key, "state": "evaluation", "attempt": attempt_number + 1,
                         "attempt_id": attempt_id, "runtime_origin_unproven": runtime_uncertain(result), "result": result})
        _checkpoint(root, "evaluation-finish", pause_at)
    if result is None:
        result = {"execution": {"status": "NOT_EXECUTED", "failure": {"code": "ATTEMPT_BUDGET_EXHAUSTED"}},
                  "verification": {"verdict": "INCONCLUSIVE", "failure_code": "EXECUTION_FAILED",
                  "verification_strength": "UNKNOWN", "summary": "Started/interrupted evaluation budget exhausted; no new execution"}}
    if runtime_uncertain(result):
        result = {**result, "verification": {**result["verification"], "verdict": "INCONCLUSIVE",
                  "failure_code": "EXECUTION_FAILED", "verification_strength": "UNKNOWN",
                  "summary": "Runtime timeout/availability did not establish semantic correctness; origin unproven after bounded evaluation retry"}}
    completed = {"arm": arm, "key": list(key), "state": "completed", "feedback_assisted": retry > 0,
                  "baseline_key": (retry_input.get("baseline_key") or retry_input["key"]) if retry_input else None,
                  "previous_key": retry_input["key"] if retry_input else None, **result}
    _checkpoint(root, "finalization", pause_at)
    append(ledger, completed)
    return completed


def finish_arm(root: Path, provider: Provider, arm: str) -> None:
    with exclusive_lock(root / "writer.lock"):
        provider.unload()
        append(root / "calls.jsonl", {"arm": arm, "state": "unloaded", "model": provider.metadata()})
