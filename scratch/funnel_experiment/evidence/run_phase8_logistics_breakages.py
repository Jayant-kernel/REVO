"""Falsify the active logistics v2 oracle with source-derived mutations."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import inspect
import io
import json
import sys
import textwrap
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification import business_oracles
from verified_data_factory.verification.oracle_registry import ORACLES, OracleEntry

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
TASK = generate_task(load_builtin_registry().get("sql.funnel.logistics_parcel_delivery", 2), 1)
ORACLE_KEY = (TASK.template_id, TASK.template_version)
ORIGINAL = ORACLES[ORACLE_KEY]
Oracle = Callable[[Any, Any], Any]

VARIANTS: dict[str, tuple[tuple[tuple[str, str], ...], str]] = {
    "drop_sequence_tie_break": ((("(row[\"occurred_at\"], row[\"sequence\"], row[\"record_id\"])", "(row[\"occurred_at\"],)"),), "test_same_timestamp_uses_sequence"),
    "allow_non_consecutive_steps": ((("if [row[\"status\"] for row in chain] != steps:", "if False:"),), "test_non_consecutive_in_scope_scan_interrupts_then_later_chain_counts"),
    "allow_gap_over_bound": ((("if all(right - left <= max_gap for left, right in pairwise(times)):", "if True:"),), "test_gap_at_boundary_counts_and_gap_over_boundary_does_not"),
    "sum_later_complete_chain": ((("                break", "                continue"),), "test_first_complete_chain_per_parcel_is_used"),
    "drop_year_filter": ((("if str(row[\"occurred_at\"])[:4] == str(req[\"year\"]) and row[\"status\"] in in_scope:", "if row[\"status\"] in in_scope:"),), "test_year_and_out_of_scope_rows_do_not_create_depot"),
    "include_out_of_scope_depot": ((("if str(row[\"occurred_at\"])[:4] == str(req[\"year\"]) and row[\"status\"] in in_scope:", "if str(row[\"occurred_at\"])[:4] == str(req[\"year\"]):"),), "test_year_and_out_of_scope_rows_do_not_create_depot"),
}


def _mutant(name: str, replacements: tuple[tuple[str, str], ...]) -> tuple[Oracle, str, str]:
    source = textwrap.dedent(inspect.getsource(business_oracles.logistics_parcel_delivery_v2))
    mutated = source
    for old, new in replacements:
        if mutated.count(old) != 1:
            raise ValueError(f"{name}: expected one source occurrence")
        mutated = mutated.replace(old, new, 1)
    namespace = dict(vars(business_oracles))
    exec(compile(mutated, f"<phase8:{name}>", "exec"), namespace)  # noqa: S102
    return namespace["logistics_parcel_delivery_v2"], hashlib.sha256(source.encode()).hexdigest(), hashlib.sha256(mutated.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results: list[dict[str, Any]] = []
    try:
        for name, (replacements, test_name) in VARIANTS.items():
            mutant, source_hash, mutant_hash = _mutant(name, replacements)
            ORACLES[ORACLE_KEY] = OracleEntry(mutant, ORIGINAL.oracle_version, f"semantic-mutant:{name}")
            nodeid = f"tests/test_logistics_funnel_v2.py::{test_name}"
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                exit_code = pytest.main(["-q", "-p", "no:cacheprovider", nodeid])
            results.append({"breakage": name, "named_failing_test": nodeid, "classification": "KILLED_WRONG_ANSWER" if exit_code == pytest.ExitCode.TESTS_FAILED else "SURVIVED", "oracle_source_sha256": source_hash, "mutant_source_sha256": mutant_hash, "pytest_exit_code": int(exit_code), "pytest_output_tail": output.getvalue().splitlines()[-8:]})
    finally:
        ORACLES[ORACLE_KEY] = ORIGINAL
    args.output.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if all(row["classification"] == "KILLED_WRONG_ANSWER" for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
