"""Coverage-aware, model-free differential fuzzing for the SaaS v2 contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_business_tasks import SAAS_V2_CHAINED_JOIN_SQL
from tests.test_saas_v2_differential_sql import RECURSIVE_SQL
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.oracle_registry import get_oracle

BEHAVIORS = (
    "complete_sequence",
    "year_exclusion",
    "out_of_order_step",
    "skipped_step",
    "early_payment",
    "repeated_payment",
    "cancelled_ignored",
    "zero_completion_segment",
    "multiple_entities",
    "input_shuffle",
    "same_timestamp_sequence_order",
    "unmatched_amount",
    "payment_amount",
    "out_of_scope_status",
)


def _task():
    return generate_task(load_builtin_registry().get("sql.funnel.saas_activation_payment"), 1)


def _row(
    record_id: int,
    entity_id: int,
    group_key: str,
    status: str,
    sequence: int,
    amount: int = 0,
    year: int = 2025,
    second: int | None = None,
) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "entity_id": entity_id,
        "group_key": group_key,
        "occurred_at": f"{year}-01-01 00:00:{sequence if second is None else second:02d}",
        "status": status,
        "amount": amount,
        "sequence": sequence,
    }


def _case(seed: int, index: int, behavior: str) -> dict[str, list[dict[str, Any]]]:
    rng = random.Random(f"{seed}:{index}:{behavior}")
    group = ("north", "south", "west")[rng.randrange(3)]
    amount = rng.randint(1, 100)
    statuses = ["signup", "trial", "activation", "payment"]
    rows = [
        _row(i + 1, 1, group, status, i + 1, amount if status == "payment" else 0)
        for i, status in enumerate(statuses)
    ]

    if behavior == "year_exclusion":
        rows[0]["occurred_at"] = "2024-12-31 23:59:59"
    elif behavior == "out_of_order_step":
        rows[1]["status"], rows[2]["status"] = rows[2]["status"], rows[1]["status"]
    elif behavior == "skipped_step":
        rows.pop(1)
    elif behavior == "early_payment":
        rows.insert(1, _row(5, 1, group, "payment", 2, amount + 100))
        for row in rows[2:]:
            row["sequence"] += 1
    elif behavior == "repeated_payment":
        rows.append(_row(5, 1, group, "payment", 5, amount + 100))
    elif behavior == "cancelled_ignored":
        rows.insert(2, _row(5, 1, group, "cancelled", 3, amount + 100))
        for row in rows[3:]:
            row["sequence"] += 1
    elif behavior == "zero_completion_segment":
        rows = [_row(1, 1, group, "signup", 1)]
    elif behavior == "multiple_entities":
        rows.extend(
            _row(i + 5, 2, group, status, i + 1, amount if status == "payment" else 0)
            for i, status in enumerate(statuses)
        )
    elif behavior == "input_shuffle":
        rng.shuffle(rows)
    elif behavior == "same_timestamp_sequence_order":
        for row in rows:
            row["occurred_at"] = "2025-01-01 00:00:00"
    elif behavior == "unmatched_amount":
        for row in rows[:-1]:
            row["amount"] = rng.randint(101, 200)
    elif behavior == "payment_amount":
        rows[-1]["amount"] = amount
    elif behavior == "out_of_scope_status":
        rows.insert(2, _row(5, 1, group, "other", 3, amount + 100))
        for row in rows[3:]:
            row["sequence"] += 1
    return {"account_funnel": rows}


def _execute(task: Any, tables: dict[str, list[dict[str, Any]]], sql: str) -> list[list[Any]]:
    connection = materialize_duckdb(task.schema_, tables)
    try:
        return [
            [str(value) if isinstance(value, (date, datetime)) else value for value in row]
            for row in connection.execute(sql).fetchall()
        ]
    finally:
        connection.close()


def _oracle(task: Any, tables: dict[str, list[dict[str, Any]]]) -> list[list[Any]]:
    return get_oracle(task.template_id, task.template_version).fn(task.requirements, tables).rows


def _invalid_inputs_are_rejected(task: Any) -> dict[str, str]:
    invalid_cases = {
        "duplicate_order_key": {
            "account_funnel": [
                _row(1, 1, "north", "signup", 1),
                _row(2, 1, "north", "trial", 1),
            ]
        },
        "inconsistent_group": {
            "account_funnel": [
                _row(1, 1, "north", "signup", 1),
                _row(2, 1, "south", "trial", 2),
            ]
        },
    }
    rejected: dict[str, str] = {}
    for name, tables in invalid_cases.items():
        try:
            _oracle(task, tables)
        except ValueError as error:
            rejected[name] = str(error)
        else:
            raise AssertionError(f"invalid input accepted: {name}")
    return rejected


def _reduce_divergence(
    task: Any, tables: dict[str, list[dict[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    rows = list(tables["account_funnel"])
    for row in list(rows):
        candidate = [item for item in rows if item is not row]
        candidate_tables = {"account_funnel": candidate}
        expected = _oracle(task, candidate_tables)
        if (
            _execute(task, candidate_tables, RECURSIVE_SQL) != expected
            or _execute(task, candidate_tables, SAAS_V2_CHAINED_JOIN_SQL) != expected
        ):
            rows = candidate
    return {"account_funnel": rows}


def run(threshold_path: Path, output_path: Path) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    threshold_bytes = threshold_path.read_bytes()
    threshold = json.loads(threshold_bytes)
    if threshold_path.stat().st_mtime >= started_at.timestamp():
        raise ValueError("threshold file must predate the fuzz run")
    task = _task()
    cases_per_seed = int(threshold["cases_per_seed"])
    minimum = int(threshold["behavior_minimum_per_seed"])
    seeds = [int(seed) for seed in threshold["seeds"]]
    if cases_per_seed < len(BEHAVIORS) * minimum:
        raise ValueError("case budget cannot satisfy behavior coverage threshold")

    coverage: dict[str, dict[str, int]] = {}
    divergences: list[dict[str, Any]] = []
    for seed in seeds:
        scheduled = [behavior for behavior in BEHAVIORS for _ in range(minimum)]
        rng = random.Random(seed)
        scheduled.extend(rng.choice(BEHAVIORS) for _ in range(cases_per_seed - len(scheduled)))
        rng.shuffle(scheduled)
        counts = {behavior: 0 for behavior in BEHAVIORS}
        for index, behavior in enumerate(scheduled):
            tables = _case(seed, index, behavior)
            expected = _oracle(task, tables)
            recursive = _execute(task, tables, RECURSIVE_SQL)
            chained = _execute(task, tables, SAAS_V2_CHAINED_JOIN_SQL)
            counts[behavior] += 1
            if recursive != expected or chained != expected:
                divergences.append(
                    {
                        "seed": seed,
                        "case_index": index,
                        "behavior": behavior,
                        "tables": tables,
                        "oracle": expected,
                        "recursive": recursive,
                        "chained_join": chained,
                        "reduced_tables": _reduce_divergence(task, tables),
                    }
                )
        coverage[str(seed)] = counts
    uncovered = {
        seed: {name: count for name, count in counts.items() if count < minimum}
        for seed, counts in coverage.items()
    }
    uncovered = {seed: counts for seed, counts in uncovered.items() if counts}
    report = {
        "evidence_id": "phase6-saas-v2-coverage-aware-fuzz-20261005",
        "contract": "sql.funnel.saas_activation_payment@2",
        "started_at": started_at.isoformat(),
        "threshold": {
            "path": str(threshold_path),
            "sha256": hashlib.sha256(threshold_bytes).hexdigest(),
            "modified_at": datetime.fromtimestamp(threshold_path.stat().st_mtime, UTC).isoformat(),
            "content": threshold,
        },
        "comparison": {
            "oracle": "business_oracles.saas_activation_payment",
            "recursive_reference": "tests.test_saas_v2_differential_sql.RECURSIVE_SQL",
            "chained_join": "tests.test_business_tasks.SAAS_V2_CHAINED_JOIN_SQL",
        },
        "coverage": coverage,
        "invalid_inputs_rejected": _invalid_inputs_are_rejected(task),
        "divergences": divergences,
        "status": "PASS" if not uncovered and not divergences else "FAIL",
    }
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.threshold, args.output)
    print(json.dumps({"status": report["status"], "output": str(args.output)}, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
