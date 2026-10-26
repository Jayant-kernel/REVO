"""Executed manufacturing-scrap random cases and private challenge catalog."""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engineering_campaign import OUT, ROOT, safety, stamp, write_new
from engineering_rejudge import evaluate
from engineering_score import digest
from phase3_diagnostic import _reference_sql

from verified_data_factory.task_engine import generate_task, load_builtin_registry


def generate(seed: int, index: int) -> dict:
    rng = random.Random(f"scrap:{seed}:{index}")
    rows = []
    for i in range(rng.randint(20, 60)):
        rows.append({"record_id": i + 1, "entity_id": rng.randint(1, 8), "group_key": f"g{rng.randrange(5)}",
                     "occurred_at": f"{rng.choice([2024, 2025, 2026])}-01-01 00:00:00",
                     "status": rng.choice(["eligible", "ineligible"]), "amount": rng.randint(-20, 20), "sequence": i + 1})
    return {"production_runs": rows}


def observe(tables: dict) -> set:
    rows = tables["production_runs"]
    found = {"multiple_groups"} if len({r["group_key"] for r in rows}) > 1 else set()
    if any(r["amount"] < 0 for r in rows):
        found.add("negative_amounts")
    if any(r["amount"] == 0 for r in rows):
        found.add("zero_amounts")
    if any(r["status"] == "ineligible" for r in rows):
        found.add("excluded_status")
    if any(not r["occurred_at"].startswith("2025") for r in rows):
        found.add("excluded_year")
    if any(r["status"] == "eligible" and r["occurred_at"].startswith("2025") for r in rows):
        found.add("eligible_rows")
    return found


def main() -> None:
    safety()
    task = generate_task(load_builtin_registry().get("sql.aggregation.manufacturing_line_scrap", 1), 94001)
    reference = _reference_sql()[task.template_id]
    alternatives = [reference,
                    "WITH scoped AS (SELECT * FROM production_runs WHERE status='eligible' AND EXTRACT(YEAR FROM occurred_at)=2025) SELECT group_key, SUM(amount) AS total_amount FROM scoped GROUP BY group_key ORDER BY group_key ASC",
                    "SELECT group_key, SUM(amount) AS total_amount FROM production_runs WHERE occurred_at >= TIMESTAMP '2025-01-01' AND occurred_at < TIMESTAMP '2026-01-01' AND status='eligible' GROUP BY group_key ORDER BY group_key ASC"]
    wrong = [reference.replace("SUM(amount)", expression) for expression in
             ("COUNT(amount)", "AVG(amount)", "MAX(amount)", "MIN(amount)", "SUM(DISTINCT amount)",
              "SUM(ABS(amount))", "SUM(amount)+1", "SUM(amount)-1", "SUM(amount)*2", "SUM(amount)*0", "SUM(amount)+10", "SUM(amount)-10")]
    wrong += [reference.replace("=2025", "=2024"), reference.replace("=2025", "=2026"),
              reference.replace("status='eligible'", "status='ineligible'"), reference.replace("status='eligible'", "TRUE"),
              reference.replace("EXTRACT(YEAR FROM occurred_at)=2025", "TRUE"), reference.replace("ASC", "DESC"),
              reference.replace("AS total_amount", "AS wrong_amount"), "SELECT 'constant' AS group_key, 0 AS total_amount"]
    witnesses = [task.tables] + [generate(1, i) for i in range(25)]
    challenges = []
    for index, query in enumerate(wrong):
        matched = None
        for tables in witnesses:
            outcome = evaluate(task, tables, query)
            if outcome["classification"] == "KILLED_WRONG_ANSWER":
                matched = {"query_index": index, "sql": query, "witness": tables, "outcome": outcome}
                break
        if matched is None:
            raise ValueError(f"wrong query {index} has no semantic witness")
        challenges.append(matched)
    coverage = {}
    failures = []
    for seed in (1, 43, 94001):
        counts = Counter()
        for index in range(300):
            tables = generate(seed, index)
            counts.update(observe(tables))
            for alt, sql in enumerate(alternatives):
                outcome = evaluate(task, tables, sql)
                if outcome["classification"] != "MATCH":
                    failures.append({"seed": seed, "case": index, "alternative": alt, "tables": tables, "outcome": outcome})
        coverage[str(seed)] = dict(counts)
    write_new(OUT / "phase7-scrap-coverage.json", {"created_at": stamp(), "contract_id": task.template_id, "contract_version": 1,
             "cases": 900, "qualified_alternatives": len(alternatives) if not failures else 0,
             "alternative_sql": alternatives, "wrong_challenges": challenges, "observed_random_coverage": coverage,
             "failures": failures, "independence": "differential verification", "excluded_from_model_inputs": True,
             "source_hashes": {p: digest(ROOT / p) for p in ("scripts/engineering_scrap_coverage.py",
                 "src/verified_data_factory/verification/comparator.py", "src/verified_data_factory/verification/business_oracles.py",
                 "tests/test_business_tasks.py")}})
    print(json.dumps({"cases": 900, "wrong_witnesses": len(challenges), "alternatives": len(alternatives),
                      "coverage": coverage, "failures": len(failures)}, indent=2))


if __name__ == "__main__":
    main()
