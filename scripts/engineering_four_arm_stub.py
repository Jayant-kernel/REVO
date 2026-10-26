"""Four locked arms, real SQL evaluator, stub outputs only; no model network."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.engineering_pipeline import finish_arm, run_slot
from tests.test_business_tasks import SAAS_V2_CHAINED_JOIN_SQL
from verified_data_factory.generation import build_sql_prompt
from verified_data_factory.local_lock import exclusive_lock
from verified_data_factory.task_engine import generate_task, load_builtin_registry

CONTRACT = "sql.funnel.saas_activation_payment"


class Stub:
    def __init__(self, root: Path, name: str) -> None:
        self.root, self.name = root, name
    def metadata(self) -> dict[str, Any]:
        return {"name": self.name, "digest": "stub-only", "quantization": "NOT_APPLICABLE",
                "context_size": 16384, "thinking": False, "temperature": 0.3, "top_p": 0.9}
    def generate(self, prompt: str, seed: int) -> str:
        with (self.root / "provider-calls.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"seed": seed, "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest()}) + "\n")
        # Stub responses deliberately exercise real passing and failing SQL.
        return "SELECT 1" if seed in {100, 102, 104} else SAAS_V2_CHAINED_JOIN_SQL
    def unload(self) -> None:
        with (self.root / "provider-unloads.txt").open("a", encoding="utf-8") as handle:
            handle.write(self.name + "\n")


def run(root: Path) -> dict[str, Any]:
    with exclusive_lock(root / "campaign.lock"):
        return _run_locked(root)


def _run_locked(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    summaries = []
    cumulative_calls = 0
    for name in ("pinned", "qwen"):
        model_root = root / name
        model_root.mkdir(exist_ok=True)
        provider = Stub(model_root, "stub-" + name)
        calls_path = model_root / "provider-calls.jsonl"
        prior_calls = len(calls_path.read_text().splitlines()) if calls_path.exists() else 0
        ledger_path = model_root / "calls.jsonl"
        prior_rows = [json.loads(line) for line in ledger_path.read_text().splitlines() if line] if ledger_path.exists() else []
        previous_completed = {tuple(r["key"]) for r in prior_rows if r["state"] == "completed"}
        initial = []
        for index in range(6):
            initial.append(run_slot(model_root, provider, (name + "-baseline", CONTRACT, 2, index, 100 + index, 0)))
        finish_arm(model_root, provider, name + "-baseline")
        after_baseline = len(calls_path.read_text().splitlines())
        retries = []
        for base in initial:
            if base["verification"]["verdict"] != "FAIL":
                continue
            index = base["key"][3]
            for round_number in (1, 2):
                result = run_slot(model_root, provider, (name + "-feedback", CONTRACT, 2, index, 200 + index + round_number * 10, round_number), retry_input=base)
                retries.append(result)
                if result["verification"]["verdict"] != "FAIL":
                    break
                base = result
        finish_arm(model_root, provider, name + "-feedback")
        base_prompt = build_sql_prompt(generate_task(load_builtin_registry().get(CONTRACT, 2), 1))
        for path in model_root.glob("*.prompt.json"):
            receipt = json.loads(path.read_text())
            prompt = receipt["public_prompt"]
            if hashlib.sha256(prompt.encode()).hexdigest() != receipt["hash"]:
                raise ValueError("actual prompt hash does not match content")
            if not prompt.startswith(base_prompt):
                raise ValueError("prompt differs from public-task construction")
            tail = prompt[len(base_prompt):]
            if any(marker in tail for marker in ("oracle_source", "hidden", "mutants", "challenge-repair", "run_phase6")):
                raise ValueError("forbidden evidence in actual prompt suffix")
            if SAAS_V2_CHAINED_JOIN_SQL in prompt:
                raise ValueError("reference SQL leaked into prompt")
        summaries += [
            {"arm": name + "-baseline", "new_provider_calls": after_baseline - prior_calls,
             "reused_logical_results": sum(tuple(r["key"]) in previous_completed for r in initial),
             "verified_passes": sum(r["verification"]["verdict"] == "PASS" for r in initial)},
            {"arm": name + "-feedback", "new_provider_calls": len(calls_path.read_text().splitlines()) - after_baseline,
             "initial_candidates_reused": len(initial),
             "reused_logical_results": sum(tuple(r["key"]) in previous_completed for r in retries),
             "new_rescues": len({r["key"][3] for r in retries if r["verification"]["verdict"] == "PASS" and tuple(r["key"]) not in previous_completed}),
             "rescues": len({r["key"][3] for r in retries if r["verification"]["verdict"] == "PASS"}),
             "rescues_scope": "cumulative unique baseline slots"},
        ]
        ledger = [json.loads(line) for line in (model_root / "calls.jsonl").read_text().splitlines() if line]
        starts = [r for r in ledger if r["state"] == "started"]
        completed = [r for r in ledger if r["state"] == "completed"]
        physical_calls = (model_root / "provider-calls.jsonl").read_text().splitlines()
        cumulative_calls += len(physical_calls)
        new_starts = sum(r["state"] == "evaluation_started" for r in ledger) - sum(r["state"] == "evaluation_started" for r in prior_rows)
        summaries[-1]["new_evaluation_attempts_model"] = new_starts
        summaries[-1]["cumulative_evaluation_attempts_model"] = sum(r["state"] == "evaluation_started" for r in ledger)
        summaries[-1]["interrupted_attempts_model"] = sum(r["state"] == "evaluation_started" for r in ledger) - sum(r["state"] == "evaluation" for r in ledger)
        if len(starts) != len(completed) or len(starts) != len(physical_calls) or len({tuple(r["key"]) for r in completed}) != len(completed):
            raise ValueError("call accounting discrepancy")
    report = {"mode": "STUB_ONLY_REAL_EVALUATOR", "arms": summaries, "model_network_calls": 0,
               "provider_calls": sum(s["new_provider_calls"] for s in summaries),
               "provider_calls_scope": "new physical calls this invocation", "cumulative_provider_calls": cumulative_calls,
               "actual_prompt_scan": "PASS"}
    number = len(list(root.glob("report-*.json"))) + 1
    with (root / f"report-{number:06d}.json").open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    (root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.root), indent=2))
