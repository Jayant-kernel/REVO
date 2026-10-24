"""Regression checks for the scratch funnel experiment accounting."""

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "run_funnel_generation_scratch",
    Path("scripts/run_funnel_generation_scratch.py"),
)
assert SPEC and SPEC.loader
scratch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scratch)


def _row(contract="sql.funnel.checkout_paid_session", index=0, verdict="FAIL", code="RESULT_MISMATCH"):
    return {
        "contract_id": contract,
        "retry_index": 0,
        "feedback_assisted": False,
        "candidate": {"candidate_index": index, "candidate_sql": "select 1"},
        "execution": {"failure": {"message": "syntax error"}},
        "verification": {"verdict": verdict, "failure_code": code, "comparison": {"differences": []}},
    }


def test_feedback_summary_includes_reused_baseline_and_retry_pass():
    baseline = _row()
    retry = _row(verdict="PASS")
    retry.update({"retry_index": 1, "feedback_assisted": True})
    result = scratch.summary([baseline, retry], [baseline["contract_id"]])
    assert result["initial_calls"] == 1
    assert result["retry_calls"] == 1
    assert result["any_verified_pass_contracts"] == 1


def test_feedback_skips_second_retry_after_a_pass():
    baseline = _row()
    retry = _row(verdict="PASS")
    retry.update({"retry_index": 1, "feedback_assisted": True})
    counts = scratch.skipped_counts([baseline], [retry])
    assert counts["retry_pass_no_second_retry"] == 1
