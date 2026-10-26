"""Execute minimal, degenerate and cardinality profiles without claiming qualification."""
from __future__ import annotations

import argparse
import json
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.engineering_campaign import ROOT, safety, stamp
from scripts.engineering_program_audit import population
from scripts.phase3_diagnostic import _reference_sql
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.task_engine.hidden_fixtures import materialized_fixture_tables
from verified_data_factory.verification.comparator import compare
from verified_data_factory.verification.oracle_registry import get_oracle
from verified_data_factory.verification.receipt_validation import (
    digest,
    required_sources,
    runtime_identity,
)


def cardinality_stress(tables: dict[str, list[dict[str, Any]]], factor: int = 8) -> dict[str, list[dict[str, Any]]]:
    identifiers = [value for rows in tables.values() for row in rows for key, value in row.items()
                   if (key == "id" or key.endswith("_id")) and type(value) is int]
    offset = max((abs(value) for value in identifiers), default=0) + 1
    result: dict[str, list[dict[str, Any]]] = {name: [] for name in tables}
    for replica in range(factor):
        for name, rows in tables.items():
            for row in rows:
                clone = deepcopy(row)
                for key, value in clone.items():
                    if (key == "id" or key.endswith("_id")) and type(value) is int:
                        clone[key] = value + replica * offset
                result[name].append(clone)
    return result


def measure(root: Path) -> dict[str, Any]:
    registry = load_builtin_registry()
    references = _reference_sql()
    from tests.test_logistics_funnel_v2 import LOGISTICS_V2_WINDOW_SQL
    records = []
    for name, version in population():
        task = generate_task(registry.get(name, version), 94001)
        # The legacy diagnostic map intentionally retains logistics@1 SQL.
        # This campaign enumerates latest versions and must bind the v2 formulation.
        if (name, version) == ("sql.funnel.logistics_parcel_delivery", 2):
            references[name] = LOGISTICS_V2_WINDOW_SQL
        profiles: dict[str, dict[str, list[dict[str, Any]]]] = {"degenerate_empty": {table: [] for table in task.tables},
                    "minimal_prefix": {table: rows[:1] for table, rows in task.tables.items()},
                    "boundary_seed": task.tables, "cardinality_clone_8": cardinality_stress(task.tables)}
        outcomes: list[dict[str, Any]] = []
        for label, tables in profiles.items():
            connection = None
            try:
                connection = materialize_duckdb(task.schema_, tables)
                canonical = materialized_fixture_tables(task, connection)
                expected = get_oracle(name, version).fn(task.requirements, canonical)
                if name not in references:
                    raise ValueError("no retained reference formulation")
                connection.execute("SET threads=1")
                connection.execute("SET memory_limit='128MB'")
                began = time.monotonic()
                cursor = connection.execute(references[name])
                description = cursor.description
                rows = [list(row) for row in cursor.fetchall()]
                elapsed = (time.monotonic() - began) * 1000
                comparison = compare(expected, [column[0] for column in description], rows,
                                     column_types=[str(column[1]) for column in description])
                outcomes.append({"profile": label, "status": "MATCH" if comparison.match else "DIVERGENCE",
                    "rows_by_table": {table: len(values) for table, values in canonical.items()},
                    "tables": canonical, "expected": expected.model_dump(mode="json"),
                    "actual": {"columns": [c[0] for c in description], "column_types": [str(c[1]) for c in description], "rows": rows},
                    "comparison": comparison.model_dump(mode="json"),
                    "elapsed_ms_correct_query_only": elapsed if comparison.match else None})
            except Exception as exc:  # noqa: BLE001 — retain blocked/error profiles, never count them as PASS
                outcomes.append({"profile": label, "status": "BLOCKED_OR_EXECUTION_ERROR", "reason": str(exc),
                                 "elapsed_ms_correct_query_only": None})
            finally:
                if connection is not None:
                    connection.close()
        passing_cardinalities = {tuple(sorted(case["rows_by_table"].items())) for case in outcomes if case["status"] == "MATCH"}
        records.append({"contract_id": name, "contract_version": version, "family": task.family,
                        "profiles": outcomes, "distinct_passing_cardinalities": len(passing_cardinalities),
                        "reference_sql": references.get(name),
                        "remaining": "skew/sparsity/fanout/long-history targeted profiles and complete semantic qualification remain required"})
    sources = required_sources()
    for relative in ("scripts/engineering_realism_profiles.py", "scripts/engineering_program_audit.py",
                     "scripts/phase3_diagnostic.py", "tests/test_business_tasks.py", "tests/test_legacy_adversarial.py",
                     "tests/test_logistics_funnel_v2.py"):
        sources[relative] = digest(root / relative)
    return {"created_at": stamp(), "population_count": len(records), "contracts": records,
            "source_hashes": sources, "runtime": runtime_identity(),
            "qualification_claim": "NONE", "authorship": "differential verification; independent authorship unproven",
            "limitations": "Identifier cloning preserves observed references by common translation, not a proof of every business-domain constraint. Rejected profiles remain blocked. Minimal prefixes are cases, not proven minimal counterexamples."}


def main() -> None:
    safety()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = measure(ROOT)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)
    print(json.dumps({"population": report["population_count"], "three_cardinalities_observed":
                      sum(c["distinct_passing_cardinalities"] >= 3 for c in report["contracts"]), "qualified": "NOT_CLAIMED"}))


if __name__ == "__main__":
    main()
