"""Execute the previously surviving logistics@2 scope-drop on a valid counterexample."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.engineering_campaign import ROOT, safety, stamp
from tests.test_logistics_funnel_v2 import LOGISTICS_V2_WINDOW_SQL
from verified_data_factory.generation.models import CandidateSolution, GenerationConfig
from verified_data_factory.sandbox import SandboxExecutor, load_config
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.comparator import compare
from verified_data_factory.verification.mutations import OPERATORS
from verified_data_factory.verification.oracle_registry import get_oracle
from verified_data_factory.verification.receipt_validation import (
    digest,
    required_sources,
    runtime_identity,
)


def main() -> None:
    safety()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    task = generate_task(load_builtin_registry().get("sql.funnel.logistics_parcel_delivery", 2), 94001)
    rows: list[dict[str, Any]] = []
    for entity, year, group, amount in ((1, 2025, "in", 7), (2, 2024, "excluded", 23)):
        for sequence, status in enumerate(task.requirements["funnel_steps"], 1):
            rows.append({"record_id": len(rows) + 1, "entity_id": entity, "group_key": group,
                "occurred_at": f"{year}-01-01 00:{sequence * 10:02d}:00", "sequence": sequence,
                "status": status, "amount": amount if status == "delivered" else 0})
    tables = {"parcel_scans": rows}
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, tables)
    wrong = OPERATORS["where-clause-drop"].apply(task, LOGISTICS_V2_WINDOW_SQL)
    assert wrong is not None and wrong != LOGISTICS_V2_WINDOW_SQL
    executor = SandboxExecutor(load_config(ROOT / "configs/sandbox_production.yaml"))
    outcomes = []
    for label, sql in (("correct", LOGISTICS_V2_WINDOW_SQL), ("wrong", wrong)):
        candidate = CandidateSolution(candidate_id=f"{task.task_id}.reference-{label}-{hashlib.sha256(sql.encode()).hexdigest()[:12]}",
            task_id=task.task_id, model="manual-reference-sql", model_revision="1", prompt_version="none",
            generation_schema_version="1.0", provider="reference-authored", endpoint_id="none", candidate_index=0,
            raw_response=sql, candidate_sql=sql, generation_config=GenerationConfig(temperature=0.0, top_p=1.0, max_tokens=1),
            generation_timestamp=datetime.now(UTC).isoformat(), generation_duration_ms=0,
            finish_reason="manual reference/transform; no provider generation")
        execution = executor.execute_on_rows(task, candidate, tables)
        assert execution.status == "SUCCEEDED" and execution.result_data is not None, execution
        data = execution.result_data
        comparison = compare(expected, [c.name for c in data.columns], data.rows,
                             column_types=[c.type for c in data.columns])
        assert comparison.match is (label == "correct")
        outcomes.append({"label": label, "sql": sql, "candidate": candidate.model_dump(mode="json"),
                         "execution": execution.model_dump(mode="json"), "comparison": comparison.model_dump(mode="json")})
    sources = required_sources()
    for relative in ("scripts/engineering_logistics_counterexample.py", "tests/test_logistics_funnel_v2.py",
                     "tests/verify_testkit.py", "configs/sandbox_production.yaml"):
        sources[relative] = digest(ROOT / relative)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump({"created_at": stamp(), "contract_id": task.template_id, "contract_version": 2,
                   "task": task.model_dump(mode="json", by_alias=True), "tables": tables,
                   "expected": expected.model_dump(mode="json"), "outcomes": outcomes,
                   "source_hashes": sources, "runtime": runtime_identity(),
                   "disposition": "SEMANTIC_KILL_ON_VALID_ALTERNATE_FIXTURE; historical survival retained",
                   "role": "EXPOSED_DIAGNOSTIC; not unseen evaluation or a training dataset member",
                   "qualification": "NOT_ESTABLISHED; one counterexample does not lift quarantine",
                   "authorship": "differential verification; independent authorship unproven"}, handle, indent=2)
    print("Correct MATCH; scope-drop KILLED_WRONG_ANSWER by out-of-year complete chain. Quarantine retained.")


if __name__ == "__main__":
    main()
