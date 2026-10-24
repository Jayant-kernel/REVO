import json
from pathlib import Path

from scripts.funnel_experiment_runner import Call, Runner, public_feedback


def _calls() -> list[Call]: return [Call("a","d","c",i,10+i,0.3,"p",False,0) for i in range(2)]
def _prompts(calls): return {(c.contract_id,c.candidate_index, c.retry_round): "Write DuckDB SQL" for c in calls}

def test_resume_never_repeats_completed_call(tmp_path: Path) -> None:
    calls, seen = _calls(), []
    runner = Runner(tmp_path, lambda prompt, timeout: seen.append(prompt) or "SELECT 1")
    runner.run(calls[:1], _prompts(calls)); runner.run(calls, _prompts(calls))
    assert len(seen) == 2

def test_cap_stops_cleanly(tmp_path: Path) -> None:
    rows = Runner(tmp_path, lambda prompt, timeout: "SELECT 1", arm_cap_s=0).run(_calls(), _prompts(_calls()))
    receipts = [json.loads(line) for line in (tmp_path / "call-log.jsonl").read_text().splitlines()]
    assert rows == [] and receipts == [{"arm": "a", "reason": "arm_cap", "status": "stopped"}]

def test_feedback_never_contains_hidden_verifier_data() -> None:
    prompt = public_feedback("FAIL", "binder error", "expected [1], got []")
    assert "hidden" not in prompt.lower() and "mutation" not in prompt.lower() and "property" not in prompt.lower()


def test_visible_retry_is_logged_and_resumes_without_duplicate_calls(tmp_path: Path) -> None:
    calls, seen = _calls()[:1], []
    runner = Runner(tmp_path, lambda prompt, timeout: seen.append(prompt) or "SELECT 1")
    verifier = lambda call, output: {"verdict": "RESULT_MISMATCH", "execution": "NONE", "visible_difference": "expected [1], got []"}
    rows = runner.run_visible_retries(calls, _prompts(calls), "a-feedback", verifier=verifier)
    assert [row["retry_round"] for row in rows] == [0, 1, 2]
    assert len(seen) == 3
    runner.run_visible_retries(calls, _prompts(calls), "a-feedback", verifier=verifier)
    assert len(seen) == 3


def test_prompt_leak_is_rejected_before_provider_call(tmp_path: Path) -> None:
    call = _calls()[0]
    runner = Runner(tmp_path, lambda prompt, timeout: (_ for _ in ()).throw(AssertionError("called")))
    try:
        runner.run([call], {(call.contract_id, call.candidate_index, 0): "include hidden fixture"})
    except ValueError as error:
        assert "hidden" in str(error)
    else:
        raise AssertionError("expected feedback boundary failure")
