"""Real child termination cannot reset evaluation budgets or authorize feedback."""
import json
import subprocess
import sys

import pytest

from scripts.engineering_pipeline import run_slot
from scripts.engineering_stub_worker import Stub
from tests.test_engineering_pipeline import KEY, ROOT, wait


def kill_at(root, boundary):
    marker = root / (boundary + "-paused")
    if marker.exists():
        marker.unlink()
    child = subprocess.Popen([sys.executable, "scripts/engineering_stub_worker.py", "--root", str(root),
                              "--pause", boundary], cwd=ROOT)
    try:
        wait(marker, timeout=120)
    finally:
        child.terminate()
        child.wait(timeout=10)


def test_two_interrupted_starts_exhaust_the_budget(tmp_path):
    kill_at(tmp_path, "evaluation-start")
    kill_at(tmp_path, "evaluation-start")
    result = run_slot(tmp_path, Stub(tmp_path, False), KEY)
    assert result["verification"]["verdict"] == "INCONCLUSIVE"
    assert result["execution"]["status"] == "NOT_EXECUTED"
    rows = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert sum(r["state"] == "evaluation_started" for r in rows) == 2
    assert sum(r["state"] == "evaluation" for r in rows) == 0
    assert (tmp_path / "provider-count.txt").read_text().splitlines() == ["call"]
    assert run_slot(tmp_path, Stub(tmp_path, False), KEY) == result


@pytest.mark.parametrize("boundary", ["evaluation-finish", "finalization"])
def test_finished_evaluation_is_reused_after_process_kill(tmp_path, boundary):
    kill_at(tmp_path, boundary)
    result = run_slot(tmp_path, Stub(tmp_path, False), KEY)
    assert result["verification"]["verdict"] == "PASS"
    rows = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert sum(r["state"] == "evaluation_started" for r in rows) == 1
    assert sum(r["state"] == "evaluation" for r in rows) == 1
    assert (tmp_path / "provider-count.txt").read_text().splitlines() == ["call"]


@pytest.mark.parametrize("verdict", ["INCONCLUSIVE", "PASS", "UNKNOWN", None])
def test_only_exact_fail_can_authorize_feedback(tmp_path, verdict):
    with pytest.raises(ValueError, match="failed baseline"):
        run_slot(tmp_path, Stub(tmp_path, False), ("stub-feedback", *KEY[1:-1], 1),
                 retry_input={"verification": {"verdict": verdict}})
    assert not (tmp_path / "provider-count.txt").exists()


def test_unknown_arm_and_cross_provider_pair_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="arm/provider"):
        run_slot(tmp_path, Stub(tmp_path, False), ("invented-arm", *KEY[1:]))
    with pytest.raises(ValueError, match="arm/provider"):
        run_slot(tmp_path, Stub(tmp_path, False), ("pinned-baseline", *KEY[1:]))
    assert not (tmp_path / "provider-count.txt").exists()
