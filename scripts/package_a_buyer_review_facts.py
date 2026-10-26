"""Read-only buyer-review measurements; outputs contain no candidate SQL."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def measure(root: Path) -> dict:
    run = root / "runs/premium-qualification-080"
    golden = rows(run / "quality/export/golden.jsonl")
    tasks = {task["task_id"]: task for task in rows(run / "tasks/tasks.jsonl")}
    candidates = {
        result["candidate_solution"]["candidate_id"]: result["candidate_solution"]
        for batch in rows(run / "candidates/candidates.jsonl")
        for result in batch.get("results", []) if result.get("candidate_solution")
    }
    selected_tasks = [tasks[candidates[g["candidate_id"]]["task_id"]] for g in golden]
    counts = Counter(t["family"] for t in selected_tasks)
    experiment = root / "scratch/funnel-generation-experiment/phase13-authorized-current-runner-20261006-r3"
    ledger = rows(experiment / "calls.jsonl")
    arms = {}
    for arm in sorted({call["arm"] for call in ledger}):
        selected = [call for call in ledger if call["arm"] == arm]
        arms[arm] = {
            "actual_calls": len(selected),
            "verified_passes": sum(call.get("verification", {}).get("verdict") == "PASS" for call in selected),
            "failure_codes": dict(Counter(str(call.get("verification", {}).get("failure_code", call.get("error", "NONE"))) for call in selected)),
            "distinct_sql_hashes": len({hashlib.sha256(call.get("candidate", {}).get("candidate_sql", "").encode()).hexdigest() for call in selected}),
            "generation_seed_count": len({call.get("sampling_seed") for call in selected}),
            "wall_clock_seconds": sum(call.get("wall_clock_ms", 0) for call in selected) / 1000,
            "rows_with_prompt_hash": sum("prompt_hash" in call or "prompt_hash" in call.get("candidate", {}).get("provider_metadata", {}) for call in selected),
            "rows_with_explicit_contract_version": sum("contract_version" in call for call in selected),
        }
    index = json.loads((root / "scratch/funnel_experiment/evidence/phase10-contract-evidence-index.json").read_text())
    return {
        "frozen_selected_population": {
            "golden_rows": len(golden), "required_release_rows": 80,
            "family_counts": dict(sorted(counts.items())),
            "unique_instruction_texts": len({g["instruction"] for g in golden}),
            "templates": len({(t["template_id"], t["template_version"]) for t in selected_tasks}),
            "note": "Frozen historical rows are not forward-version qualification evidence.",
        },
        "readiness_index": {
            "contracts": len(index["contracts"]),
            "status_counts": dict(Counter(c["status"] for c in index["contracts"])),
            "fully_verified_with_no_journal_records": [c["contract_id"] for c in index["contracts"] if c["status"] == "FULLY_VERIFIED" and not c["journal_evidence"]],
        },
        "phase13_actual_calls": {"total": len(ledger), "arms": arms},
        "limitations": ["No model call or frozen mutation occurred.", "These counts are evidence measurements, not a score or release approval."],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    facts = measure(Path(__file__).resolve().parents[1])
    args.output.write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(facts, indent=2))


if __name__ == "__main__":
    main()
