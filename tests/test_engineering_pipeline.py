import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts.engineering_pipeline import IndeterminateCall, execute_sql, finish_arm, run_slot
from scripts.engineering_stub_worker import Stub
from verified_data_factory.task_engine import generate_task, load_builtin_registry

ROOT = Path(__file__).resolve().parents[1]
KEY = ("stub-baseline", "sql.funnel.saas_activation_payment", 2, 0, 1, 0)


def wait(path, timeout=20):
    deadline = time.monotonic() + timeout
    while not path.exists():
        if time.monotonic() > deadline:
            raise AssertionError(f"worker did not reach {path.name}")
        time.sleep(0.05)


@pytest.mark.parametrize("pause", ["provider", "response"])
def test_actual_process_kill_preserves_provider_accounting(tmp_path, pause):
    child = subprocess.Popen([sys.executable, "scripts/engineering_stub_worker.py", "--root", str(tmp_path), "--pause", pause], cwd=ROOT)
    try:
        wait(tmp_path / ("provider-paused" if pause == "provider" else "response-paused"))
    finally:
        child.terminate()
        child.wait(timeout=10)
    provider = Stub(tmp_path, False)
    if pause == "provider":
        with pytest.raises(IndeterminateCall):
            run_slot(tmp_path, provider, KEY)
    else:
        result = run_slot(tmp_path, provider, KEY)
        assert result["verification"]["verdict"] == "PASS"
        assert run_slot(tmp_path, provider, KEY) == result
        finish_arm(tmp_path, provider, "stub-baseline")
    assert (tmp_path / "provider-count.txt").read_text().splitlines() == ["call"]


def test_cap_stops_before_generation(tmp_path):
    with pytest.raises(TimeoutError):
        run_slot(tmp_path, Stub(tmp_path, False), KEY, cap_seconds=0)
    assert not (tmp_path / "provider-count.txt").exists()


def test_retries_cannot_follow_success_or_exceed_two_rounds(tmp_path):
    with pytest.raises(ValueError):
        run_slot(tmp_path, Stub(tmp_path, False), (*KEY[:-1], 3))
    with pytest.raises(ValueError):
        run_slot(tmp_path, Stub(tmp_path, False), (*KEY[:-1], 1), retry_input={"verification": {"verdict": "PASS"}})


def test_select_one_is_rejected_by_the_real_evaluator():
    task = generate_task(load_builtin_registry().get(KEY[1], KEY[2]), 1)
    result = execute_sql(task, "SELECT 1", 1)
    assert result["verification"]["verdict"] == "FAIL"
    assert result["verification"]["failure_code"] == "RESULT_MISMATCH"


def test_changed_protocol_is_rejected_without_another_provider_call(tmp_path):
    run_slot(tmp_path, Stub(tmp_path, False), KEY)
    with pytest.raises(ValueError, match="protocol"):
        run_slot(tmp_path, Stub(tmp_path, False), KEY, cap_seconds=1)
    assert len((tmp_path / "provider-count.txt").read_text().splitlines()) == 1


def test_local_adapter_sends_locked_sampling_and_unload_without_network(monkeypatch):
    from scripts.engineering_pipeline import LocalOllama
    model, digest = next(iter(LocalOllama.ALLOWED.items()))
    provider = LocalOllama(model)
    observed = []
    def request(path, payload):
        observed.append((path, payload))
        if path == "/api/tags":
            return {"models": [{"name": model, "digest": digest}]}
        if path == "/api/show":
            return {"details": {"quantization_level": "TEST_ONLY"}}
        return {"response": "SELECT 1"}
    monkeypatch.setattr(provider, "request", request)
    assert provider.generate("public-only", 43) == "SELECT 1"
    assert observed[-1][1]["options"]["seed"] == 43
    assert observed[-1][1]["options"]["temperature"] == 0.3
    assert observed[-1][1]["options"]["top_p"] == 0.9
    assert observed[-1][1]["think"] is False
    provider.unload()
    assert observed[-1][1]["keep_alive"] == 0


def test_local_digest_mismatch_stops_before_generation(monkeypatch):
    from scripts.engineering_pipeline import LocalOllama
    provider = LocalOllama(next(iter(LocalOllama.ALLOWED)))
    monkeypatch.setattr(provider, "request", lambda path, payload: {"models": []})
    with pytest.raises(ValueError, match="missing or digest"):
        provider.generate("public-only", 1)


def test_untrusted_retry_receipt_is_rejected_before_prompt_persistence(tmp_path):
    forged = {"state": "completed", "key": list(KEY),
              "verification": {"verdict": "FAIL", "failure_code": "RESULT_MISMATCH",
                               "comparison": {"differences": ["FORBIDDEN_SENTINEL_TEST"]}}}
    with pytest.raises(ValueError, match="exact completed ledger"):
        run_slot(tmp_path, Stub(tmp_path, False), ("stub-feedback", *KEY[1:-1], 1), retry_input=forged)
    assert list(tmp_path.glob("*.prompt.json")) == []
