from scripts.engineering_pipeline import run_slot
from scripts.engineering_stub_worker import Stub

KEY = ("stub-baseline", "sql.funnel.saas_activation_payment", 2, 0, 1, 0)


def timeout_result():
    return {"execution": {"status": "SUCCEEDED"}, "verification": {"verdict": "FAIL",
            "failure_code": "HIDDEN_MISMATCH", "hidden": {"cases": [{"status": "FAIL", "detail": "hidden execution TIMEOUT"}]}}}


def test_transient_timeout_retries_evaluation_not_generation(tmp_path, monkeypatch):
    import scripts.engineering_pipeline as module
    observed = []
    def evaluate(task, sql, seed):
        observed.append(sql)
        return timeout_result() if len(observed) == 1 else {"execution": {"status": "SUCCEEDED"}, "verification": {"verdict": "PASS", "failure_code": None}}
    monkeypatch.setattr(module, "execute_sql", evaluate)
    result = run_slot(tmp_path, Stub(tmp_path, False), KEY)
    assert result["verification"]["verdict"] == "PASS"
    assert len(observed) == 2
    assert (tmp_path / "provider-count.txt").read_text().splitlines() == ["call"]


def test_persistent_timeout_is_inconclusive_after_one_retry(tmp_path, monkeypatch):
    import scripts.engineering_pipeline as module
    calls = []
    def evaluate(task, sql, seed):
        calls.append(sql)
        return timeout_result()
    monkeypatch.setattr(module, "execute_sql", evaluate)
    result = run_slot(tmp_path, Stub(tmp_path, False), KEY)
    assert len(calls) == 2
    assert result["verification"]["verdict"] == "INCONCLUSIVE"
    assert len((tmp_path / "provider-count.txt").read_text().splitlines()) == 1
