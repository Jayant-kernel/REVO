"""Executor tests with FakeDockerRunner (no daemon required)."""

import json

from verified_data_factory.generation import FakeProvider, GenerationConfig, generate_candidate
from verified_data_factory.sandbox import (
    TERMINAL_STATUSES,
    FakeDockerRunner,
    SandboxConfig,
    SandboxExecutor,
    execute_candidate,
)
from verified_data_factory.task_engine import canonical_json, generate_task

CONFIG = SandboxConfig()


def _ok_payload(rows=((1,),), columns=("a",)):
    return {
        "status": "ok",
        "duckdb_version": "1.5.5",
        "columns": [{"name": c, "type": "INTEGER"} for c in columns],
        "rows": [list(r) for r in rows],
        "rows_returned": len(rows),
        "truncated": False,
    }


def _pair(registry, sql="SELECT customer_id FROM customers;"):
    task = generate_task(registry.get("sql.joins.simple"), seed=101)
    candidate = generate_candidate(
        task, FakeProvider(script=[sql]), GenerationConfig()
    ).candidate_solution
    assert candidate is not None
    return task, candidate


def test_success_path(registry):
    task, candidate = _pair(registry, "SELECT customer_id, SUM(amount) FROM orders GROUP BY 1;")
    runner = FakeDockerRunner(output_files={"result.json": _ok_payload()})
    result = SandboxExecutor(CONFIG, runner).execute(task, candidate)
    assert result.status == "SUCCEEDED"
    assert result.result_data is not None
    assert result.result_data.rows == [[1]]
    assert result.exit_code == 0
    assert result.task_id == task.task_id
    assert result.candidate_id == candidate.candidate_id
    assert result.sandbox_config_version == "1.0"
    assert result.duckdb_version == "1.5.5"
    assert result.sandbox_image == CONFIG.image
    assert result.execution_id.startswith(candidate.candidate_id)
    assert len(runner.removed) == 1
    assert runner.killed == []


def test_sql_error_is_execution_error(registry):
    task, candidate = _pair(registry)
    payload = {
        "status": "error",
        "duckdb_version": "1.5.5",
        "error": {"type": "BinderException", "message": "no such table"},
    }
    result = SandboxExecutor(
        CONFIG, FakeDockerRunner(output_files={"result.json": payload})
    ).execute(task, candidate)
    assert result.status == "EXECUTION_ERROR"
    assert result.failure is not None and result.failure.code == "EXECUTION_ERROR"
    assert "no such table" in result.failure.message
    assert result.result_data is None


def test_binding_mismatch_rejected_without_container(registry):
    task, candidate = _pair(registry)
    other = generate_task(registry.get("sql.joins.simple"), seed=102)
    candidate = candidate.model_copy(update={"task_id": other.task_id})
    runner = FakeDockerRunner(output_files={"result.json": _ok_payload()})
    result = SandboxExecutor(CONFIG, runner).execute(task, candidate)
    assert result.status == "POLICY_REJECTED"
    assert result.failure is not None and result.failure.code == "POLICY_REJECTED"
    assert runner.calls == []  # no container ever created


def test_empty_sql_rejected(registry):
    task, candidate = _pair(registry)
    candidate = candidate.model_copy(update={"candidate_sql": "   "})
    runner = FakeDockerRunner(output_files={"result.json": _ok_payload()})
    result = SandboxExecutor(CONFIG, runner).execute(task, candidate)
    assert result.status == "POLICY_REJECTED"
    assert result.failure is not None and result.failure.code == "INVALID_INPUT"
    assert runner.calls == []


def test_multi_statement_rejected_without_container(registry):
    task, candidate = _pair(registry, "SELECT 1; DROP TABLE customers;")
    runner = FakeDockerRunner(output_files={"result.json": _ok_payload()})
    result = SandboxExecutor(CONFIG, runner).execute(task, candidate)
    assert result.status == "POLICY_REJECTED"
    assert result.failure is not None
    assert result.failure.detail.get("policy_reason") == "MULTIPLE_STATEMENTS"
    assert runner.calls == []


def test_startup_failure_maps_to_start_failed(registry):
    task, candidate = _pair(registry)
    runner = FakeDockerRunner(fail_on="run", output_files={"result.json": _ok_payload()})
    result = SandboxExecutor(CONFIG, runner).execute(task, candidate)
    assert result.status == "SANDBOX_ERROR"
    assert result.failure is not None and result.failure.code == "SANDBOX_START_FAILED"
    assert len(runner.removed) == 1  # best-effort removal still attempted


def test_timeout_kills_and_cleans(registry):
    task, candidate = _pair(registry)
    runner = FakeDockerRunner(hang=True, output_files={"result.json": _ok_payload()})
    result = SandboxExecutor(SandboxConfig(timeout_seconds=1), runner).execute(task, candidate)
    assert result.status == "TIMEOUT"
    assert result.failure is not None and result.failure.code == "TIMEOUT"
    assert len(runner.killed) == 1 and len(runner.removed) == 1


def test_oom_exit_maps_to_resource_limit(registry):
    task, candidate = _pair(registry)
    runner = FakeDockerRunner(exit_code=137, output_files={"result.json": _ok_payload()})
    result = SandboxExecutor(CONFIG, runner).execute(task, candidate)
    assert result.status == "RESOURCE_LIMIT"
    assert result.failure is not None and result.failure.code == "RESOURCE_LIMIT"


def test_huge_output_maps_to_result_limit(registry):
    task, candidate = _pair(registry, "SELECT * FROM big_table;")
    rows = [[i] for i in range(200)]
    payload = _ok_payload(rows=rows)
    cfg = SandboxConfig(max_result_rows=10)
    result = SandboxExecutor(cfg, FakeDockerRunner(output_files={"result.json": payload})).execute(
        task, candidate
    )
    assert result.status == "SUCCEEDED"
    assert result.result_data is not None
    assert result.result_data.truncated is True
    assert result.result_data.rows_returned == 10


def test_oversized_serialization_maps_to_result_limit(registry):
    task, candidate = _pair(registry)
    payload = _ok_payload(rows=[[i, "pad-to-grow-serialized-bytes-" + str(i)] for i in range(100)])
    cfg = SandboxConfig(max_result_rows=100000, max_result_bytes=1024)
    result = SandboxExecutor(cfg, FakeDockerRunner(output_files={"result.json": payload})).execute(
        task, candidate
    )
    assert result.status == "RESULT_LIMIT"
    assert result.failure is not None and result.failure.code == "RESULT_LIMIT"


def test_cleanup_failure_overrides_success(registry):
    task, candidate = _pair(registry)

    class BadRemove(FakeDockerRunner):
        def remove(self, container_id: str) -> None:
            raise OSError("cannot remove")

    result = SandboxExecutor(
        CONFIG, BadRemove(output_files={"result.json": _ok_payload()})
    ).execute(task, candidate)
    assert result.status == "SANDBOX_ERROR"
    assert result.failure is not None and result.failure.code == "SANDBOX_CLEANUP_ERROR"


def test_inputs_never_mutated(registry):
    task, candidate = _pair(registry)
    task_before, cand_before = canonical_json(task), candidate.model_dump_json()
    SandboxExecutor(CONFIG, FakeDockerRunner(output_files={"result.json": _ok_payload()})).execute(
        task, candidate
    )
    assert canonical_json(task) == task_before
    assert candidate.model_dump_json() == cand_before


def test_results_only_terminal_and_verdict_free(registry):
    outcomes = [
        FakeDockerRunner(output_files={"result.json": _ok_payload()}),
        FakeDockerRunner(
            output_files={
                "result.json": {"status": "error", "error": {"type": "X", "message": "y"}}
            }
        ),
        FakeDockerRunner(fail_on="run", output_files={"result.json": _ok_payload()}),
        FakeDockerRunner(hang=True, output_files={"result.json": _ok_payload()}),
        FakeDockerRunner(exit_code=137, output_files={"result.json": _ok_payload()}),
    ]
    for i, runner in enumerate(outcomes):
        task = generate_task(registry.get("sql.joins.simple"), seed=200 + i)
        candidate = generate_candidate(
            task, FakeProvider(script=["SELECT 1;"]), GenerationConfig()
        ).candidate_solution
        assert candidate is not None
        result = SandboxExecutor(SandboxConfig(timeout_seconds=1), runner).execute(task, candidate)
        assert result.status in TERMINAL_STATUSES, result.status
        dumped = json.dumps(result.model_dump(mode="json"))
        for banned in ("is_correct", "CORRECT", "INCORRECT", "VERIFIED", "oracle"):
            assert banned not in dumped


def test_execute_candidate_helper(registry):
    task, candidate = _pair(registry)
    result = execute_candidate(
        task, candidate, CONFIG, FakeDockerRunner(output_files={"result.json": _ok_payload()})
    )
    assert result.status == "SUCCEEDED"


def test_execute_on_rows_delivers_custom_rows(registry):
    """Custom rows reach the container payload; canonical fixture intact."""
    import json as json_mod

    task, candidate = _pair(registry)
    custom = {name: [] for name in task.tables}
    runner = FakeDockerRunner(output_files={"result.json": _ok_payload()})
    result = SandboxExecutor(CONFIG, runner).execute_on_rows(task, candidate, custom)
    assert result.status == "SUCCEEDED"
    assert runner.payloads, "payload must be delivered to the container"
    envelope = json_mod.loads(runner.payloads[0].decode("utf-8"))
    assert set(envelope) == {"fixture", "sql", "run"}
    assert envelope["fixture"]["tables"] == custom
    assert envelope["sql"] == candidate.candidate_sql
    assert task.tables["customers"], "canonical fixture untouched"
