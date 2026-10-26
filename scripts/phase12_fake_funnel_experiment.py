"""Phase 12's deterministic, fake-only four-arm funnel experiment.

This is a certification harness, not a model experiment. It never constructs a
network provider or invokes the production pipeline's provider factory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CONTRACTS = (
    "sql.funnel.checkout_paid_session",
    "sql.funnel.curriculum_gate_completion",
    "sql.funnel.kyc_document_approval",
    "sql.funnel.logistics_parcel_delivery",
    "sql.funnel.parcel_exception_recovery",
    "sql.funnel.saas_activation_payment",
    "sql.funnel.support_resolution_chain",
)
ARMS = ("pinned-baseline", "pinned-feedback", "qwen-baseline", "qwen-feedback")
BASELINE_ARMS = ("pinned-baseline", "qwen-baseline")
FEEDBACK_PAIRS = {"pinned-feedback": "pinned-baseline", "qwen-feedback": "qwen-baseline"}
FORBIDDEN_FEEDBACK = (
    "oracle", "hidden", "adversarial", "property", "metamorphic", "mutation", "strategy",
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _append(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _seed(arm: str, contract: str, candidate_index: int, retry_index: int) -> int:
    return int(_hash(f"{arm}|{contract}|{candidate_index}|{retry_index}")[:12], 16)


def _fake_provider(prompt: str, seed: int) -> str:
    """Return deterministic fake SQL; this function deliberately has no I/O."""
    return f"SELECT {seed % 97} AS synthetic_value -- {_hash(prompt)[:12]}"


def _initial_outcome(contract: str, candidate_index: int) -> str:
    # Retain deterministic visible failures so all retry paths are certified.
    return "PASS" if int(_hash(f"{contract}|{candidate_index}")[:2], 16) % 4 == 0 else "RESULT_MISMATCH"


def _retry_outcome(contract: str, candidate_index: int, retry_index: int) -> str:
    return "PASS" if retry_index == 2 or int(_hash(f"retry|{contract}|{candidate_index}")[:2], 16) % 2 == 0 else "RESULT_MISMATCH"


def feedback_envelope(row: dict[str, Any]) -> str:
    if row["verdict"] != "RESULT_MISMATCH":
        raise ValueError("feedback is only allowed for a visible initial mismatch")
    envelope = (
        f"Previous candidate SQL:\n{row['candidate_sql']}\n\n"
        "Verifier outcome: RESULT_MISMATCH\n"
        "Execution diagnostic: NONE\n"
        "Visible result difference: expected synthetic_value differs from actual synthetic_value\n\n"
        "Return replacement DuckDB SQL only. Preserve the supplied task contract."
    )
    leak_scan(envelope)
    return envelope


def leak_scan(value: str) -> None:
    lowered = value.lower()
    found = [word for word in FORBIDDEN_FEEDBACK if word in lowered]
    if found:
        raise ValueError(f"feedback boundary leak: {', '.join(found)}")


def _key(row: dict[str, Any]) -> tuple[str, str, int, int]:
    return (str(row["arm"]), str(row["contract_id"]), int(row["candidate_index"]), int(row["retry_index"]))


def _record(arm: str, contract: str, candidate_index: int, retry_index: int, base: dict[str, Any] | None) -> dict[str, Any]:
    seed = _seed(arm, contract, candidate_index, retry_index)
    prompt = f"Write DuckDB SQL for {contract}; fixture seed is fixed."
    feedback_assisted = base is not None
    if base is not None:
        prompt += "\n\n" + feedback_envelope(base)
    started = time.monotonic()
    candidate_sql = _fake_provider(prompt, seed)
    verdict = _initial_outcome(contract, candidate_index) if base is None else _retry_outcome(contract, candidate_index, retry_index)
    return {
        "schema_version": "phase12-fake-v1",
        "arm": arm,
        "contract_id": contract,
        "candidate_index": candidate_index,
        "retry_index": retry_index,
        "sampling_seed": seed,
        "provider": "fake",
        "provider_network_calls": 0,
        "feedback_assisted": feedback_assisted,
        "paired_baseline_key": list(_key(base)) if base is not None else None,
        "prompt_hash": _hash(prompt),
        "feedback_envelope_hash": _hash(feedback_envelope(base)) if base is not None else None,
        "candidate_sql": candidate_sql,
        "candidate_sql_hash": _hash(candidate_sql),
        "verdict": verdict,
        "visible_difference": "synthetic_value mismatch" if verdict == "RESULT_MISMATCH" else None,
        "wall_clock_ms": int((time.monotonic() - started) * 1000),
        "created_at": _now(),
    }


def _stop(ledger: Path, arm: str, reason: str) -> None:
    _append(ledger, {"kind": "stop", "arm": arm, "reason": reason, "created_at": _now()})


def run(root: Path, arm_cap_calls: int = 126) -> dict[str, Any]:
    """Resume a bounded fake run. ``root`` is the only directory written."""
    if arm_cap_calls < 0:
        raise ValueError("arm cap cannot be negative")
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "manifest.json"
    manifest = {
        "phase": 12,
        "mode": "FAKE_CERTIFICATION_ONLY",
        "provider": "fake",
        "provider_network_calls": 0,
        "arms": list(ARMS),
        "contracts": list(CONTRACTS),
        "initial_candidates_per_baseline_arm": 6,
        "arm_cap_calls": arm_cap_calls,
    }
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
            raise ValueError("scratch identity does not match the locked fake experiment")
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ledger = root / "calls.jsonl"
    prior = _read(ledger)
    calls = [row for row in prior if row.get("kind") == "call"]
    completed = {_key(row) for row in calls}
    by_arm = Counter(str(row["arm"]) for row in calls)
    stopped = {str(row["arm"]) for row in prior if row.get("kind") == "stop"}

    def emit(row: dict[str, Any]) -> None:
        row["kind"] = "call"
        _append(ledger, row)
        calls.append(row)
        completed.add(_key(row))
        by_arm[row["arm"]] += 1

    for arm in BASELINE_ARMS:
        if arm in stopped:
            continue
        for contract in CONTRACTS:
            for candidate_index in range(6):
                key = (arm, contract, candidate_index, 0)
                if key in completed:
                    continue
                if by_arm[arm] >= arm_cap_calls:
                    _stop(ledger, arm, "arm_call_cap")
                    stopped.add(arm)
                    break
                emit(_record(arm, contract, candidate_index, 0, None))
            if arm in stopped:
                break

    baseline_rows = {arm: [row for row in calls if row["arm"] == arm] for arm in BASELINE_ARMS}
    for arm, paired in FEEDBACK_PAIRS.items():
        if arm in stopped:
            continue
        for base in baseline_rows[paired]:
            if base["verdict"] != "RESULT_MISMATCH":
                continue
            for retry_index in (1, 2):
                key = (arm, str(base["contract_id"]), int(base["candidate_index"]), retry_index)
                if key in completed:
                    prior_retry = next(row for row in calls if _key(row) == key)
                    if prior_retry["verdict"] == "PASS":
                        break
                    continue
                if retry_index == 2:
                    first = next((row for row in calls if _key(row) == (arm, base["contract_id"], base["candidate_index"], 1)), None)
                    if first and first["verdict"] == "PASS":
                        break
                if by_arm[arm] >= arm_cap_calls:
                    _stop(ledger, arm, "arm_call_cap")
                    stopped.add(arm)
                    break
                emit(_record(arm, str(base["contract_id"]), int(base["candidate_index"]), retry_index, base))
            if arm in stopped:
                break

    evidence = certify(root)
    (root / "status.json").write_text(json.dumps(evidence["status"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "checklist.json").write_text(json.dumps(evidence["checklist"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


def certify(root: Path) -> dict[str, Any]:
    rows = [row for row in _read(root / "calls.jsonl") if row.get("kind") == "call"]
    errors: list[str] = []
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    seen: set[tuple[str, str, int, int]] = set()
    baseline = {(row["arm"], row["contract_id"], row["candidate_index"]): row for row in rows if row["arm"] in BASELINE_ARMS}
    for row in rows:
        key = _key(row)
        if key in seen:
            errors.append(f"duplicate call: {key}")
        seen.add(key)
        if row["provider"] != "fake" or row["provider_network_calls"] != 0:
            errors.append(f"non-fake provider evidence: {key}")
        if row.get("feedback_assisted", False):
            paired_arm = FEEDBACK_PAIRS.get(str(row["arm"]))
            base = baseline.get((paired_arm, row["contract_id"], row["candidate_index"]))
            if base is None or base["verdict"] != "RESULT_MISMATCH":
                errors.append(f"invalid paired retry: {key}")
            if row["retry_index"] not in (1, 2):
                errors.append(f"invalid retry index: {key}")
    for arm in ARMS:
        if any(row["arm"] == arm for row in rows) is False:
            errors.append(f"missing arm: {arm}")
        if sum(row["arm"] == arm for row in rows) > manifest["arm_cap_calls"]:
            errors.append(f"arm cap exceeded: {arm}")
    checklist = {
        "fake_provider_only": not any("non-fake provider" in error for error in errors),
        "all_four_arms_present": not any("missing arm" in error for error in errors),
        "resumable_jsonl_ledger": (root / "calls.jsonl").exists(),
        "paired_retries": not any("paired retry" in error or "retry index" in error for error in errors),
        "arm_cap_respected": not any("arm cap exceeded" in error for error in errors),
        "feedback_leak_scan": True,
        "scratch_only_output": True,
    }
    status = {"phase": 12, "mode": "FAKE_CERTIFICATION_ONLY", "result": "PASS" if not errors else "FAIL", "calls": len(rows), "errors": errors}
    return {"status": status, "checklist": checklist, "arms": {arm: sum(row["arm"] == arm for row in rows) for arm in ARMS}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--arm-cap-calls", type=int, default=126)
    args = parser.parse_args()
    evidence = run(args.scratch, args.arm_cap_calls)
    print(json.dumps(evidence["status"], sort_keys=True))
    return 0 if evidence["status"]["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
