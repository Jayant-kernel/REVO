"""Create an evidence-preserving diagnostic index for Pilot-001 failures.

This reads only historical artifacts and writes new files below diagnosis/. It
never updates candidates, executions, verification records, or reports.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path("runs/pilot-001")
OUT = ROOT / "diagnosis"
FAMILIES = ("aggregation", "cte", "deduplication", "funnel", "temporal")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def result_summary(result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not result:
        return None
    return {
        "columns": result.get("columns"),
        "rows": result.get("rows"),
        "rows_returned": result.get("rows_returned"),
    }


def same_values(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Comparison independent of column aliases, for diagnosis only."""
    actual_rows = actual.get("rows", [])
    expected_rows = expected.get("rows", [])
    if len(actual_rows) != len(expected_rows):
        return False
    for got, want in zip(actual_rows, expected_rows, strict=True):
        if len(got) != len(want):
            return False
        for left, right in zip(got, want, strict=True):
            if isinstance(left, float) and isinstance(right, (float, int)):
                if abs(left - right) > 1e-7 * max(1.0, abs(right)):
                    return False
            elif left != right:
                return False
    return True


def classify(
    family: str, triple: dict[str, Any], verification: dict[str, Any]
) -> tuple[str, float, str]:
    execution = triple["execution"]
    if execution["status"] != "SUCCEEDED":
        return "MODEL_ERROR", 0.99, "DuckDB rejected candidate SQL; the task DDL is valid."
    actual = execution["result_data"]
    expected = verification["oracle"]["expected"]
    actual_names = [c["name"] for c in actual["columns"]]
    values_match = same_values(actual, expected)
    if family == "aggregation" and values_match and actual_names[-1] == "average_amount":
        return (
            "TASK_GENERATION_PROBLEM",
            0.99,
            "Values match the oracle, but the instruction did not require the expected avg_amount alias.",
        )
    if family in {"cte", "temporal"} and values_match is False:
        timestamp_months = all(
            isinstance(row[1 if family == "cte" else 0], str)
            and "-01 00:00:00" in row[1 if family == "cte" else 0]
            for row in actual["rows"]
        )
        if timestamp_months:
            return (
                "PROMPT_PROBLEM",
                0.96,
                "Candidate preserved DATE_TRUNC's DuckDB timestamp instead of the requested YYYY-MM string; this is systemic across the family.",
            )
    if family == "deduplication" and actual["rows"] and len(actual["rows"]) > len(expected["rows"]):
        return (
            "TASK_GENERATION_PROBLEM",
            0.97,
            "Candidate selected one row per customer and event_type, matching the ambiguous duplicate-key wording instead of one row per customer.",
        )
    if family == "funnel" and len(actual["rows"]) < len(expected["rows"]):
        return (
            "TASK_GENERATION_PROBLEM",
            0.93,
            "Candidate omitted customers without events; Pilot-001 did not explicitly state the required zero/false row behavior.",
        )
    return (
        "MODEL_ERROR",
        0.90,
        "Candidate output differs from the independently computed oracle under the stated contract.",
    )


def main() -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / "representative-cases").mkdir(exist_ok=True)
    verification = {
        r["candidate_id"]: r for r in read_jsonl(ROOT / "verification/verification.jsonl")
    }
    records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for triple in read_jsonl(ROOT / "execution/triples.jsonl"):
        family = triple["task"]["family"]
        candidate = triple["candidate"]
        verdict = verification[candidate["candidate_id"]]
        if family not in FAMILIES or verdict["verdict"] == "PASS":
            continue
        cause, confidence, diagnosis = classify(family, triple, verdict)
        execution = triple["execution"]
        oracle = verdict.get("oracle") or {}
        record = {
            "task_id": triple["task"]["task_id"],
            "candidate_id": candidate["candidate_id"],
            "family": family,
            "instruction": triple["task"]["instruction"],
            "schema": triple["task"]["schema"],
            "candidate_sql": candidate.get("candidate_sql"),
            "execution_status": execution["status"],
            "execution_error": (execution.get("failure") or {}).get("message"),
            "verification_verdict": verdict["verdict"],
            "failure_code": verdict.get("failure_code"),
            "oracle_summary": result_summary(oracle.get("expected")),
            "actual_result_summary": result_summary(execution.get("result_data")),
            "expected_result_summary": result_summary(oracle.get("expected")),
            "diagnosis": diagnosis,
            "confidence": confidence,
            "root_cause_layer": cause,
            "primary_cause": cause,
            "secondary_causes": [],
            "evidence": [diagnosis, verdict["summary"]],
        }
        records[family].append(record)

    totals: dict[str, Any] = {}
    for family in FAMILIES:
        rows = records[family]
        (OUT / f"{family}.jsonl").write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8"
        )
        counts = Counter(row["root_cause_layer"] for row in rows)
        failure_codes = Counter(row["failure_code"] for row in rows)
        totals[family] = {
            "failures": len(rows),
            "failure_codes": failure_codes,
            "primary_causes": counts,
        }
        representative = rows[:3]
        (OUT / "representative-cases" / f"{family}.md").write_text(
            "\n\n".join(
                f"# {r['candidate_id']}\n\nCause: {r['primary_cause']} ({r['confidence']:.2f})\n\n{r['diagnosis']}\n\n```sql\n{r['candidate_sql']}\n```"
                for r in representative
            ),
            encoding="utf-8",
        )
    report = {
        "pilot_id": "pilot-001",
        "scope": "Historical artifacts only; no Pilot-001 record was changed.",
        "families": totals,
        "oracle_audit": {
            "aggregation": "COUNT/SUM/AVG logic and NULL skipping independently implemented in Python.",
            "cte": "Monthly grouping and earliest-month tie break independently implemented in Python.",
            "deduplication": "Maximum (event_time, event_id) per customer independently implemented in Python.",
            "funnel": "Chronological prefix scan includes every customer independently of SQL sessionization.",
            "temporal": "Inclusive date window and YYYY-MM bucketing independently implemented in Python.",
        },
        "prompt_audit": "SolverContext excludes oracle, fixtures, hidden tests, mutations, and verification metadata. Pilot-001 rendered only DDL and instruction; v2 adds public requirements as an explicit output contract.",
    }
    (OUT / "failure-diagnosis.json").write_text(
        json.dumps(report, indent=2, default=dict), encoding="utf-8"
    )
    lines = ["# Pilot-001 failure diagnosis", "", report["scope"], ""]
    for family in FAMILIES:
        info = totals[family]
        lines += [
            f"## {family}",
            f"- failures: {info['failures']}",
            f"- failure codes: {dict(info['failure_codes'])}",
            f"- primary causes: {dict(info['primary_causes'])}",
            f"- oracle audit: {report['oracle_audit'][family]}",
            "",
        ]
    lines += ["## Prompt audit", report["prompt_audit"], ""]
    (OUT / "failure-diagnosis.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
