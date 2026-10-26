"""Resumable scratch runner; local Ollama is opt-in and dry-run remains default."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

FORBIDDEN_FEEDBACK = ("hidden", "mutation", "property", "oracle", "adversarial", "metamorphic")
Provider = Callable[[str, int], str]
Verifier = Callable[["Call", str], dict[str, object]]


@dataclass(frozen=True)
class Call:
    arm: str
    model_digest: str
    contract_id: str
    candidate_index: int
    seed: int
    temperature: float
    prompt_hash: str
    feedback_assisted: bool
    retry_round: int

    @property
    def key(self) -> tuple[str, str, int, int, int]:
        return (self.arm, self.contract_id, self.candidate_index, self.seed, self.retry_round)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _read(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _append(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()


def _no_leak(value: str) -> None:
    found = [word for word in FORBIDDEN_FEEDBACK if word in value.lower()]
    if found:
        raise ValueError(f"forbidden verifier data in prompt: {', '.join(found)}")


def public_feedback(status: str, execution: str, visible_diff: str) -> str:
    """Create the only feedback format accepted by a retry prompt."""
    feedback = (
        f"Verifier outcome: {status}\nExecution diagnostic: {execution}\n"
        f"Visible result difference: {visible_diff}\nReturn DuckDB SQL only."
    )
    _no_leak(feedback)
    return feedback


class OllamaProvider:
    """Small local-only Ollama wrapper with observable model identity and unload."""

    def __init__(self, model: str, endpoint: str = "http://localhost:11434") -> None:
        self.model, self.endpoint = model, endpoint.rstrip("/")

    def _request(self, path: str, payload: dict[str, object], timeout_s: int) -> dict[str, object]:
        request = Request(
            self.endpoint + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_s) as response:  # nosec B310: explicit local endpoint
                body = json.load(response)
        except (OSError, URLError, ValueError) as exc:
            raise TimeoutError(f"local Ollama request failed: {exc}") from exc
        if not isinstance(body, dict):
            raise TypeError("local Ollama returned a non-object response")
        return body

    def metadata(self, timeout_s: int = 15) -> dict[str, object]:
        request = Request(self.endpoint + "/api/tags", method="GET")
        try:
            with urlopen(request, timeout=timeout_s) as response:  # nosec B310: explicit local endpoint
                body = json.load(response)
        except (OSError, URLError, ValueError) as exc:
            raise RuntimeError(f"local Ollama metadata request failed: {exc}") from exc
        models = body.get("models", []) if isinstance(body, dict) else []
        match = next((item for item in models if isinstance(item, dict) and item.get("name") == self.model), None)
        if match is None:
            raise RuntimeError(f"local Ollama model is unavailable: {self.model}")
        return {"endpoint": self.endpoint, "model": self.model, "digest": match.get("digest")}

    def __call__(self, prompt: str, timeout_s: int) -> str:
        body = self._request(
            "/api/generate", {"model": self.model, "prompt": prompt, "stream": False}, timeout_s
        )
        output = body.get("response")
        if not isinstance(output, str):
            raise TypeError("local Ollama response did not contain text")
        return output

    def unload(self, timeout_s: int = 15) -> None:
        self._request("/api/generate", {"model": self.model, "keep_alive": 0}, timeout_s)


class Runner:
    def __init__(self, root: Path, provider: Provider, arm_cap_s: float = 10800) -> None:
        self.root, self.provider, self.arm_cap_s = root, provider, arm_cap_s
        self.log = root / "call-log.jsonl"

    def completed(self) -> set[tuple[str, str, int, int, int]]:
        completed: set[tuple[str, str, int, int, int]] = set()
        for row in _read(self.log):
            key = row.get("key")
            if row.get("status") == "completed" and isinstance(key, list) and len(key) == 5:
                completed.add((str(key[0]), str(key[1]), int(key[2]), int(key[3]), int(key[4])))
        return completed

    def _elapsed(self, arm: str) -> float:
        durations = [
            value
            for row in _read(self.log)
            if row.get("status") == "completed"
            and row.get("arm") == arm
            and isinstance((value := row.get("wall_clock_s")), int | float)
        ]
        return float(sum(durations))

    def run(
        self, calls: list[Call], prompts: dict[tuple[str, int, int], str],
        timeout_s: float = 120, verifier: Verifier | None = None,
    ) -> list[dict[str, object]]:
        done, results, elapsed = self.completed(), [], {call.arm: self._elapsed(call.arm) for call in calls}
        capped: set[str] = set()
        for call in calls:
            if call.key in done or call.arm in capped:
                continue
            if elapsed[call.arm] >= self.arm_cap_s:
                _append(self.log, {"status": "stopped", "reason": "arm_cap", "arm": call.arm})
                capped.add(call.arm)
                continue
            prompt = prompts[(call.contract_id, call.candidate_index, call.retry_round)]
            _no_leak(prompt)
            _append(self.log, {"status": "started", "key": list(call.key), "arm": call.arm})
            began = time.monotonic()
            try:
                output = self.provider(prompt, int(timeout_s))
                verification = verifier(call, output) if verifier else {"verdict": "UNVERIFIED"}
                status, timeout, error = "completed", False, None
            except TimeoutError as exc:
                output, verification, status, timeout, error = "", {"verdict": "TIMEOUT"}, "completed", True, str(exc)
            except Exception as exc:  # noqa: BLE001 - provider/verifier faults must be durably visible.
                output, verification, status, timeout, error = "", {"verdict": "INFRASTRUCTURE_ERROR"}, "failed", False, f"{type(exc).__name__}: {exc}"
            duration = round(time.monotonic() - began, 6)
            row = {
                "key": list(call.key), **asdict(call), "wall_clock_s": duration, "timeout": timeout,
                "raw_output_hash": _hash(output), "raw_output": output, "verification": verification,
                "status": status, "error": error,
            }
            _append(self.log, row)
            results.append(row)
            elapsed[call.arm] += duration
            if status == "failed":
                _append(self.log, {"status": "stopped", "reason": "provider_error", "arm": call.arm})
        return results

    def run_visible_retries(
        self, baselines: list[Call], prompts: dict[tuple[str, int, int], str], feedback_arm: str,
        timeout_s: float = 120, verifier: Verifier | None = None, max_retries: int = 2,
    ) -> list[dict[str, object]]:
        """Retry only logged visible failures, preserving the baseline candidate identity."""
        rows = self.run(baselines, prompts, timeout_s, verifier)
        prior = [row for row in _read(self.log) if row.get("status") == "completed"]
        prior_by_key: dict[tuple[str, str, int, int, int], dict[str, object]] = {}
        for prior_row in prior:
            prior_key = prior_row.get("key")
            if isinstance(prior_key, list) and len(prior_key) == 5:
                prior_by_key[(
                    str(prior_key[0]), str(prior_key[1]), int(prior_key[2]),
                    int(prior_key[3]), int(prior_key[4]),
                )] = prior_row
        for row in prior:
            if row.get("arm") not in {call.arm for call in baselines}:
                continue
            verification = row.get("verification", {})
            if not isinstance(verification, dict) or verification.get("verdict") == "PASS":
                continue
            visible = verification.get("visible_difference")
            if not isinstance(visible, str):
                continue
            key = row["key"]
            if not isinstance(key, list) or len(key) != 5:
                continue
            feedback = public_feedback(str(verification.get("verdict")), str(verification.get("execution", "NONE")), visible)
            for retry_round in range(1, max_retries + 1):
                temperature = row.get("temperature")
                if not isinstance(temperature, int | float):
                    raise TypeError("completed call is missing numeric temperature")
                retry = Call(feedback_arm, str(row["model_digest"]), str(key[1]), int(key[2]), int(key[3]), float(temperature), _hash(feedback), True, retry_round)
                prompts[(retry.contract_id, retry.candidate_index, retry_round)] = feedback
                existing = prior_by_key.get(retry.key)
                if existing is not None:
                    existing_verification = existing.get("verification", {})
                    if isinstance(existing_verification, dict) and existing_verification.get("verdict") == "PASS":
                        break
                    continue
                retry_rows = self.run([retry], prompts, timeout_s, verifier)
                rows.extend(retry_rows)
                if retry_rows:
                    retry_verification = retry_rows[-1].get("verification", {})
                    if isinstance(retry_verification, dict) and retry_verification.get("verdict") == "PASS":
                        break
        return rows


def fake_provider(prompt: str, timeout_s: int) -> str:
    _ = timeout_s
    return "SELECT 1 -- " + _hash(prompt)[:8]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true", help="allow calls to an explicit local Ollama model")
    parser.add_argument("--model")
    args = parser.parse_args()
    if args.execute == args.dry_run:
        raise SystemExit("select exactly one of --dry-run or --execute")
    provider: Provider = fake_provider
    metadata: dict[str, object] = {"mode": "dry-run", "provider": "fake"}
    ollama: OllamaProvider | None = None
    arm, model_digest = "fake-baseline", "fake:dry-run"
    if args.execute:
        if not args.model:
            raise SystemExit("--execute requires --model")
        ollama = OllamaProvider(args.model)
        metadata, provider = ollama.metadata(), ollama
        digest = metadata.get("digest")
        if not isinstance(digest, str) or not digest:
            raise SystemExit("local Ollama metadata did not contain a model digest")
        arm, model_digest = "ollama-baseline", "ollama-digest:" + digest
    root = Path(args.scratch)
    _append(root / "run-events.jsonl", {"event": "launch", **metadata})
    calls = [Call(arm, model_digest, contract, index, 1000 + index, 0.3, "dry", False, 0)
             for contract in ("sql.funnel.checkout_paid_session", "sql.funnel.kyc_document_approval") for index in range(6)]
    prompts = {(call.contract_id, call.candidate_index, 0): f"Write SQL for {call.contract_id}, seed {call.seed}" for call in calls}
    try:
        rows = Runner(root, provider).run(calls, prompts)
    finally:
        if ollama is not None:
            try:
                ollama.unload()
                _append(root / "run-events.jsonl", {"event": "ollama_unloaded", **metadata})
            except RuntimeError as exc:
                _append(root / "run-events.jsonl", {"event": "ollama_unload_failed", "error": str(exc)})
    _append(root / "run-events.jsonl", {"event": "complete", "new_calls": len(rows)})
    print(json.dumps({"new_calls": len(rows), "log": str(root / "call-log.jsonl")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
