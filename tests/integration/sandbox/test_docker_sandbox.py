"""Docker integration tests: boundary properties proven in containers.

Every test here requires a Docker daemon (skipped explicitly otherwise).
Conventions: small conservative workloads; per-test SandboxConfig; the
real ``SandboxExecutor`` + ``DockerRunner`` end to end.
"""

import json
import subprocess

import pytest

from verified_data_factory.generation import FakeProvider, GenerationConfig, generate_candidate
from verified_data_factory.sandbox import (
    DockerRunner,
    SandboxConfig,
    SandboxExecutor,
    build_execution_package,
    build_execution_payload,
    fresh_container_name,
)
from verified_data_factory.task_engine import generate_task, load_builtin_registry

from .test_docker_available import requires_docker

pytestmark = pytest.mark.integration

TASK_TEMPLATE = "sql.joins.simple"
TASK_SEED = 101


def _task(registry=None):
    reg = registry or load_builtin_registry()
    return generate_task(reg.get(TASK_TEMPLATE), TASK_SEED)


def _candidate(task, sql):
    candidate = generate_candidate(
        task, FakeProvider(script=[sql]), GenerationConfig()
    ).candidate_solution
    assert candidate is not None
    return candidate


def _execute(sql, config=None, seed=TASK_SEED):
    task = generate_task(load_builtin_registry().get(TASK_TEMPLATE), seed)
    candidate = _candidate(task, sql)
    return SandboxExecutor(
        config or SandboxConfig(), DockerRunner(config or SandboxConfig())
    ).execute(task, candidate)


def _leftover_vdf_containers() -> list[str]:
    completed = subprocess.run(
        ["docker", "ps", "-a", "-q", "--filter", "name=vdf-"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return [line for line in completed.stdout.splitlines() if line.strip()]


@requires_docker
def test_legitimate_select_succeeds():
    result = _execute(
        "SELECT customer_id, COUNT(*) AS n FROM orders GROUP BY customer_id ORDER BY customer_id;"
    )
    assert result.status == "SUCCEEDED"
    assert result.result_data is not None
    assert result.result_data.rows_returned > 0
    assert [c.name for c in result.result_data.columns] == ["customer_id", "n"]
    assert result.exit_code == 0


@requires_docker
def test_invalid_sql_is_execution_error():
    result = _execute("SELECT * FROM no_such_table;")
    assert result.status == "EXECUTION_ERROR"
    assert result.failure is not None and result.failure.code == "EXECUTION_ERROR"


@requires_docker
def test_multi_statement_rejected():
    result = _execute("SELECT 1; DROP TABLE customers;")
    assert result.status == "POLICY_REJECTED"
    assert result.failure is not None
    assert result.failure.detail.get("policy_reason") == "MULTIPLE_STATEMENTS"


@requires_docker
def test_read_csv_blocked_in_container():
    result = _execute("SELECT * FROM read_csv('/etc/passwd');")
    # Policy allows bare SELECT; the DuckDB filesystem lock must stop it.
    assert result.status == "EXECUTION_ERROR"
    assert result.failure is not None
    assert "disabled" in result.failure.message or "Permission" in result.failure.message


@requires_docker
def test_install_load_attach_rejected_by_policy():
    # Constructed directly: the Phase 2 parser only emits SELECT/WITH, so
    # these payloads represent defense-in-depth at the sandbox gate itself.
    from verified_data_factory.generation.models import CandidateSolution

    task = _task()
    for sql in ("INSTALL httpfs;", "LOAD spatial;", "ATTACH '/tmp/x.db' AS x;"):
        candidate = CandidateSolution(
            candidate_id=f"{task.task_id}.adversarial.00.probe",
            task_id=task.task_id,
            model="adversarial-test",
            model_revision="test",
            prompt_version="sql-v1",
            generation_schema_version="1.0",
            provider="test",
            endpoint_id="test:adversarial",
            candidate_index=0,
            raw_response=sql,
            candidate_sql=sql,
            generation_config={"temperature": 0.0, "top_p": 1.0, "max_tokens": 10},
            generation_timestamp="2026-01-01T00:00:00+00:00",
            generation_duration_ms=0,
        )
        result = SandboxExecutor(SandboxConfig(), DockerRunner(SandboxConfig())).execute(
            task, candidate
        )
        assert result.status == "POLICY_REJECTED", sql
        assert result.failure is not None
        assert result.failure.detail.get("policy_reason") == "DISALLOWED_STATEMENT", sql


@requires_docker
def test_network_backed_access_fails():
    result = _execute("SELECT * FROM read_csv('http://169.254.169.254/latest');")
    assert result.status == "EXECUTION_ERROR"


@requires_docker
def test_timeout_kills_container():
    before = _leftover_vdf_containers()
    config = SandboxConfig(timeout_seconds=5)
    sql = (
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c WHERE x < 1000000000) "
        "SELECT sum(x) FROM c;"
    )
    result = _execute(sql, config)
    assert result.status == "TIMEOUT"
    assert result.failure is not None and result.failure.code == "TIMEOUT"
    assert _leftover_vdf_containers() == before


@requires_docker
def test_output_row_cap_truncates():
    config = SandboxConfig(max_result_rows=100)
    result = _execute("SELECT * FROM range(10000) t(i);", config)
    assert result.status == "SUCCEEDED"
    assert result.result_data is not None
    assert result.result_data.truncated is True
    assert result.result_data.rows_returned == 100


@requires_docker
def test_memory_limit_enforced_via_cgroup():
    # Direct proof the kernel enforces the configured limit: read the
    # container's own cgroup caps (fast, deterministic — unlike hoping for
    # an OOM race against DuckDB's spill logic).
    memory_mb = 96
    config = SandboxConfig(memory_mb=memory_mb, timeout_seconds=60)
    report = _run_probe(
        {"read_text": {"/sys/fs/cgroup/memory.max": 64, "/sys/fs/cgroup/memory.swap.max": 64}},
        config,
    )
    assert report["status"] == "ok"
    assert int(report["read_text"]["/sys/fs/cgroup/memory.max"].strip()) == memory_mb * 1024 * 1024
    # swap.max of 0 means swap is disabled entirely (--memory-swap == --memory).
    assert int(report["read_text"]["/sys/fs/cgroup/memory.swap.max"].strip()) == 0


@requires_docker
def test_executions_are_isolated_and_repeatable():
    sql = "SELECT COUNT(*) AS n FROM orders;"
    first = _execute(sql)
    second = _execute(sql)
    assert first.status == "SUCCEEDED" and second.status == "SUCCEEDED"
    assert first.execution_id != second.execution_id
    assert first.result_data == second.result_data


@requires_docker
def test_no_containers_left_behind():
    before = _leftover_vdf_containers()
    _execute("SELECT 1;")
    _execute("SELECT * FROM missing_table;")
    assert _leftover_vdf_containers() == before


@requires_docker
def test_result_carries_no_verdicts():
    result = _execute("SELECT 1;")
    dumped = json.dumps(result.model_dump(mode="json"))
    for banned in ("is_correct", "CORRECT", "INCORRECT", "VERIFIED", "oracle"):
        assert banned not in dumped


def _run_probe(checks: dict, config: SandboxConfig) -> dict:
    """Drive one probe container directly (boundary facts, no candidate SQL)."""
    task = generate_task(load_builtin_registry().get(TASK_TEMPLATE), TASK_SEED)
    package = build_execution_package(task)
    payload = json.loads(build_execution_payload(package, "SELECT 1;", 10).decode("utf-8"))
    payload["run"] = {"action": "probe", "checks": checks}
    runner = DockerRunner(config)
    name = fresh_container_name()
    try:
        outcome = runner.run_container(
            name, "probe", json.dumps(payload).encode("utf-8"), config.timeout_seconds
        )
        assert outcome.exit_code == 0, outcome.stderr.decode()[:500]
        return json.loads(outcome.stdout.decode("utf-8"))
    finally:
        runner.remove(name)


@requires_docker
def test_probe_non_root_user():
    report = _run_probe({}, SandboxConfig())
    assert report["status"] == "ok"
    assert report["uid"] == 10000


@requires_docker
def test_probe_no_socket_no_sentinel(tmp_path):
    sentinel = tmp_path / "host_sentinel.txt"
    sentinel.write_text("host-only", encoding="utf-8")
    report = _run_probe({"paths": [str(sentinel), "/var/run/docker.sock"]}, SandboxConfig())
    assert report["paths"][str(sentinel)] is False
    assert report["paths"]["/var/run/docker.sock"] is False


@requires_docker
def test_probe_host_secret_not_visible(monkeypatch):
    monkeypatch.setenv("TEST_SECRET_SENTINEL", "s3cr3t-probe-value")
    report = _run_probe({}, SandboxConfig())
    assert "TEST_SECRET_SENTINEL" not in report["env_keys"]
    assert not any("s3cr3t" in key for key in report["env_keys"])


@requires_docker
def test_probe_duckdb_lockdown():
    report = _run_probe(
        {
            "duckdb_lockdown": {
                "read_csv": "SELECT * FROM read_csv('/etc/passwd')",
                "install": "INSTALL httpfs",
                "load": "LOAD spatial",
            }
        },
        SandboxConfig(),
    )
    for label, outcome in report["duckdb_lockdown"].items():
        assert outcome.startswith("blocked"), (label, outcome)
