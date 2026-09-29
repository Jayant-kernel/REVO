"""Overfit + binding end-to-end (§10, §16): real Docker, real verifier."""

import subprocess

import pytest

from tests.verify_testkit import TEMPLATE_SEEDS, make_candidate, make_task
from verified_data_factory.sandbox import DockerRunner, SandboxConfig, SandboxExecutor
from verified_data_factory.verification import VerificationConfig, get_oracle, verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

from tests.integration.sandbox.test_docker_available import requires_docker

_SANDBOX = SandboxConfig(timeout_seconds=60)


@requires_docker
def test_overfit_candidate_fails_on_hidden():
    """VALUES-list constants memorize the original fixture: hidden must catch it."""
    task = make_task("sql.joins.simple", TEMPLATE_SEEDS["sql.joins.simple"])
    entry = get_oracle(task.template_id, task.template_version)
    expected = entry.fn(dict(task.requirements), task.tables)
    assert len(expected.rows) > 1
    values = ", ".join(f"({r[0]}, {r[1]})" for r in expected.rows)
    overfit_sql = (
        "SELECT * FROM (VALUES "
        + values
        + ") AS t(customer_id, total_revenue) ORDER BY total_revenue DESC;"
    )
    candidate = make_candidate(task, overfit_sql)
    execution = SandboxExecutor(_SANDBOX, DockerRunner(_SANDBOX)).execute(task, candidate)
    assert execution.status == "SUCCEEDED"  # memorizes the original fixture
    result = verify_candidate(
        task, candidate, execution, VerificationConfig(), DerivedTaskBackend(_SANDBOX)
    )
    assert result.verdict == "FAIL", (result.verdict, result.summary)
    assert result.failure_code == "HIDDEN_MISMATCH"
    assert result.hidden is not None and result.hidden.failed > 0


@requires_docker
def test_mismatched_binding_rejected_without_execution():
    task = make_task("sql.joins.simple", TEMPLATE_SEEDS["sql.joins.simple"])
    other = make_task("sql.joins.simple", TEMPLATE_SEEDS["sql.joins.simple"] + 1)
    candidate = make_candidate(other, "SELECT 1;")
    before = subprocess.run(
        ["docker", "ps", "-a", "-q", "--filter", "name=vdf-"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    ).stdout
    result = SandboxExecutor(_SANDBOX, DockerRunner(_SANDBOX)).execute(task, candidate)
    assert result.status == "POLICY_REJECTED"
    assert result.failure is not None and result.failure.code == "POLICY_REJECTED"
    after = subprocess.run(
        ["docker", "ps", "-a", "-q", "--filter", "name=vdf-"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    ).stdout
    assert after == before  # no container ever created
