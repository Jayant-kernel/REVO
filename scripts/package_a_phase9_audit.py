"""Produce read-only Phase 9 audits for generic oracles and paused Goldens."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.oracle_registry import ORACLES, get_oracle

FUNNEL_INSTRUCTION_RULES = {
    "sql.funnel.saas_activation_payment": ("occurred_at", "sequence", "zero total_amount", "neither advance nor reset"),
    "sql.funnel.logistics_parcel_delivery": ("occurred_at", "sequence", "one depot", "zero total_amount"),
    "sql.funnel.checkout_paid_session": ("event_id", "expires_at", "zero conversions", "no events"),
    "sql.funnel.curriculum_gate_completion": ("attempt_id", "zero completions", "ascending stage_number"),
    "sql.funnel.kyc_document_approval": ("review_id", "qualifies", "application_id"),
    "sql.funnel.parcel_exception_recovery": ("scan-id", "latest exception", "depot"),
    "sql.funnel.support_resolution_chain": ("event_id", "cannot complete", "different tickets"),
    "sql.funnel.completion": ("event_id", "no events", "session boundaries"),
}


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _key(template_id: str, version: int) -> str:
    return f"{template_id}@{version}"


def _candidate_tasks(run_root: Path) -> dict[str, str]:
    batches = _jsonl(run_root / "candidates" / "candidates.jsonl")
    return {
        result["candidate_solution"]["candidate_id"]: result["candidate_solution"]["task_id"]
        for batch in batches
        for result in batch.get("results", [])
        if result.get("candidate_solution")
    }


def generic_oracle_blast_radius(allowlist_path: Path) -> dict[str, Any]:
    allowlist = json.loads(allowlist_path.read_text(encoding="utf-8"))
    actual = sorted(_key(template_id, version) for (template_id, version), entry in ORACLES.items() if entry.fn.__name__ == allowlist["function"])
    allowed = sorted(allowlist["templates"])
    return {"allowlist_path": allowlist_path.as_posix(), "allowlist_match": actual == allowed, "audit_required": actual, "generic_function": allowlist["function"], "unexpected_generic_entries": sorted(set(actual) - set(allowed)), "stale_allowlist_entries": sorted(set(allowed) - set(actual)), "status": "PASS" if actual == allowed else "FAIL"}


def paused_golden_overlap(run_root: Path, generic_entries: list[str]) -> dict[str, Any]:
    goldens = _jsonl(run_root / "quality" / "export" / "golden.jsonl")
    candidate_tasks = _candidate_tasks(run_root)
    golden_tasks = {row.get("task_id", candidate_tasks[row["candidate_id"]]) for row in goldens}
    tasks = _jsonl(run_root / "tasks" / "tasks.jsonl")
    generic_pairs = {tuple(entry.rsplit("@", 1)) for entry in generic_entries}
    generic_tasks = {task["task_id"] for task in tasks if (task["template_id"], str(task["template_version"])) in generic_pairs}
    overlap = sorted(golden_tasks & generic_tasks)
    return {"mode": "READ_ONLY", "golden_count": len(goldens), "generic_task_count": len(generic_tasks), "golden_generic_task_overlap_count": len(overlap), "golden_generic_task_overlap": overlap, "status": "MEASURED_NOT_QUALIFIED"}


def _vacuity_rows(seed: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for template in load_builtin_registry().list():
        if template.family != "funnel":
            continue
        task = generate_task(template, seed)
        expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, task.tables)
        numeric = [value for row in expected.rows for value in row if isinstance(value, (int, float)) and not isinstance(value, bool)]
        vacuous = not expected.rows or (numeric and all(value == 0 for value in numeric))
        rows.append({"template_id": task.template_id, "template_version": task.template_version, "seed": seed, "expected_row_count": len(expected.rows), "numeric_value_count": len(numeric), "vacuity": "VACUOUS" if vacuous else "NON_VACUOUS"})
    return sorted(rows, key=lambda row: (str(row["template_id"]), int(row["template_version"])))


def instruction_sufficiency() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for template in load_builtin_registry().list():
        required = FUNNEL_INSTRUCTION_RULES.get(template.template_id)
        if required is None:
            continue
        instruction = template.instruction_template.lower()
        missing = [phrase for phrase in required if phrase.lower() not in instruction]
        findings.append({"template": _key(template.template_id, template.version), "missing_public_rules": missing, "status": "PASS" if not missing else "FAIL"})
    return {"findings": findings, "status": "PASS" if all(not item["missing_public_rules"] for item in findings) else "FAIL"}


def diversity_measurements(run_root: Path) -> dict[str, Any]:
    goldens = _jsonl(run_root / "quality" / "export" / "golden.jsonl")
    qualities = [row["quality"] for row in goldens]
    tasks = _jsonl(run_root / "tasks" / "tasks.jsonl")
    candidate_tasks = _candidate_tasks(run_root)
    task_schemas = {task["task_id"]: task["schema"] for task in tasks}
    golden_task_ids = [row.get("task_id", candidate_tasks[row["candidate_id"]]) for row in goldens]
    schema_fingerprints = {
        hashlib.sha256(json.dumps(task_schemas[task_id], sort_keys=True).encode()).hexdigest()
        for task_id in golden_task_ids
        if task_id in task_schemas
    }
    normalized_instructions = {" ".join(row["instruction"].lower().split()) for row in goldens}
    return {"golden_rows": len(goldens), "exact_instruction_count": len({row["instruction"] for row in goldens}), "normalized_instruction_count": len(normalized_instructions), "family_counts": dict(sorted(Counter(str(item["family"]) for item in qualities).items())), "schema_fingerprint_count": len(schema_fingerprints), "task_count_with_schema": len(set(golden_task_ids) & set(task_schemas)), "status": "MEASURED_NOT_QUALIFIED"}


def run(root: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    blast = generic_oracle_blast_radius(root / "configs" / "package_a" / "generic_oracle_allowlist.json")
    instruction = instruction_sufficiency()
    csv_paths: list[str] = []
    vacuous_count = 0
    for seed in (17, 43, 94001):
        path = output_dir / f"phase9-vacuity-seed-{seed}.csv"
        rows = _vacuity_rows(seed)
        vacuous_count += sum(row["vacuity"] == "VACUOUS" for row in rows)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        csv_paths.append(path.name)
    report = {"generic_oracle_blast_radius": blast, "instruction_sufficiency": instruction, "paused_golden_overlap": paused_golden_overlap(root / "runs" / "premium-qualification-080", blast["audit_required"]), "three_seed_vacuity_csvs": csv_paths, "three_seed_vacuous_rows": vacuous_count, "diversity_measurements": diversity_measurements(root / "runs" / "premium-qualification-080"), "status": "PASS" if blast["status"] == "PASS" and instruction["status"] == "PASS" else "FAIL"}
    (output_dir / "phase9-audit.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.root.resolve(), args.output_dir)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
