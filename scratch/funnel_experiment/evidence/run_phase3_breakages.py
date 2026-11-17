"""Falsify the active SaaS oracle with source-derived semantic mutations."""

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
TASK = generate_task(load_builtin_registry().get("sql.funnel.saas_activation_payment"), 1)
ORACLE_KEY = (TASK.template_id, TASK.template_version)
ORIGINAL = ORACLES[ORACLE_KEY]
Oracle = Callable[[Any, Any], Any]


def _source_mutant(name: str, replacements: tuple[tuple[str, str], ...]) -> tuple[Oracle, str, str]:
    """Mutate the registered implementation, failing closed on source drift."""
    source = textwrap.dedent(inspect.getsource(business_oracles.saas_activation_payment))
    original_sha256 = hashlib.sha256(source.encode()).hexdigest()
    mutated = source
    for original, replacement in replacements:
        if mutated.count(original) != 1:
            raise ValueError(f"{name}: expected one source occurrence for mutation")
        mutated = mutated.replace(original, replacement, 1)
    namespace = dict(vars(business_oracles))
    exec(compile(mutated, f"<phase3:{name}>", "exec"), namespace)  # noqa: S102 - local source mutation
    return namespace["saas_activation_payment"], original_sha256, hashlib.sha256(mutated.encode()).hexdigest()


_STEP_BLOCK = """            if progress < len(steps) and row[\"status\"] == steps[progress]:
                if progress == len(steps) - 1:
                    payment_amount = int(row[\"amount\"])
                progress += 1
"""

VARIANTS: dict[str, tuple[tuple[tuple[str, str], ...], str, str]] = {
    "last_match_instead_of_first": (
        ((_STEP_BLOCK, """            if progress < len(steps) and row[\"status\"] == steps[progress]:
                if progress == len(steps) - 1:
                    payment_amount = int(row[\"amount\"])
                progress += 1
            elif row[\"status\"] == steps[-1]:
                payment_amount = int(row[\"amount\"])
"""),),
        "test_repeated_payment_uses_first_matched_payment",
        "Overwrites the first matched completion amount with a later final-step row.",
    ),
    "drop_sequence_tie_break": (
        ((("(row[\"occurred_at\"], row[\"sequence\"], row[\"record_id\"])", "(row[\"occurred_at\"],)")),),
        "test_same_timestamp_reverse_input_uses_sequence",
        "Uses stable input order for equal timestamps instead of the required sequence key.",
    ),
    "advance_on_any_later_step": (
        ((_STEP_BLOCK, """            if row[\"status\"] in steps and steps.index(row[\"status\"]) >= progress:
                if row[\"status\"] == steps[-1]:
                    payment_amount = int(row[\"amount\"])
                progress = steps.index(row[\"status\"]) + 1
"""),),
        "test_skipped_step_never_completes",
        "Allows a later funnel step to skip required earlier steps.",
    ),
    "drop_year_filter": (
        ((("if str(row[\"occurred_at\"])[:4] == str(req[\"year\"]) and row[\"status\"] in in_scope:", "if row[\"status\"] in in_scope:")),),
        "test_2024_signup_does_not_start_2025_completion",
        "Lets an out-of-year signup start a completion.",
    ),
    "sum_all_rows": (
        ((_STEP_BLOCK, """            if progress < len(steps) and row[\"status\"] == steps[progress]:
                if progress == len(steps) - 1:
                    payment_amount += int(row[\"amount\"])
                progress += 1
            elif row[\"status\"] == steps[-1]:
                payment_amount += int(row[\"amount\"])
"""),),
        "test_repeated_payment_uses_first_matched_payment",
        "Sums all final-step rows rather than using only the first matched amount.",
    ),
    "include_out_of_scope_only_segments": (
        ((("if str(row[\"occurred_at\"])[:4] == str(req[\"year\"]) and row[\"status\"] in in_scope:", "if str(row[\"occurred_at\"])[:4] == str(req[\"year\"]):")),),
        "test_segment_without_in_scope_rows_is_absent",
        "Creates a zero segment from an out-of-scope row.",
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "breakage_table.json")
    args = parser.parse_args()
    results: list[dict[str, Any]] = []
    try:
        for name, (replacements, test_name, semantic_difference) in VARIANTS.items():
            mutant, source_sha256, mutant_sha256 = _source_mutant(name, replacements)
            ORACLES[ORACLE_KEY] = OracleEntry(mutant, ORIGINAL.oracle_version, f"semantic-mutant:{name}")
            nodeid = f"tests/test_saas_funnel_oracle.py::{test_name}"
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                exit_code = pytest.main(["-q", "-p", "no:cacheprovider", nodeid])
            results.append(
                {
                    "breakage": name,
                    "semantic_difference": semantic_difference,
                    "named_failing_test": nodeid,
                    "classification": "KILLED_WRONG_ANSWER" if exit_code == pytest.ExitCode.TESTS_FAILED else "SURVIVED",
                    "oracle_source_sha256": source_sha256,
                    "mutant_source_sha256": mutant_sha256,
                    "pytest_exit_code": int(exit_code),
                    "pytest_output_tail": output.getvalue().splitlines()[-8:],
                }
            )
    finally:
        ORACLES[ORACLE_KEY] = ORIGINAL
    args.output.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if any(result["classification"] == "SURVIVED" for result in results):
        raise SystemExit("a controlled semantic mutant survived")


if __name__ == "__main__":
    main()
