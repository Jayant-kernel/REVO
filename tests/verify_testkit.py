"""Unit-test scaffolding for verification (no Docker, no models).

``SimBackend`` simulates a *correctly behaving* candidate execution by
returning oracle-computed rows — the verifier logic under test (staging,
comparison, verdicts, evidence) is fully real; only the database is
simulated. Deviations (wrong rows, faults) are scripted explicitly per
label. Real SQL execution happens exclusively in Docker integration tests.
"""

from verified_data_factory.generation.models import CandidateSolution, GenerationConfig
from verified_data_factory.sandbox.models import ExecutionResult, ResultColumn, ResultData
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.backend import ExecutionBackend
from verified_data_factory.verification.errors import BackendError
from verified_data_factory.verification.oracle_registry import get_oracle

TEMPLATE_SEEDS = {
    "sql.joins.simple": 101,
    "sql.joins.multi": 201,
    "sql.aggregation.grouped": 301,
    "sql.cte.monthly": 401,
    "sql.subqueries.exists": 501,
    "sql.windows.ranked": 601,
    "sql.temporal.monthly": 701,
    "sql.dedup.latest": 801,
    "sql.retention.30_day": 901,
    "sql.funnel.completion": 1001,
}

_SEEDS = TEMPLATE_SEEDS


def make_task(template_id, seed=None):
    registry = load_builtin_registry()
    return generate_task(
        registry.get(template_id), seed if seed is not None else _SEEDS[template_id]
    )


def make_candidate(task, sql):
    return CandidateSolution(
        candidate_id=f"{task.task_id}.test.00.testtesttest",
        task_id=task.task_id,
        model="test-model",
        model_revision="test-rev",
        prompt_version="sql-v1",
        generation_schema_version="1.0",
        provider="test",
        endpoint_id="test:000000000000",
        candidate_index=0,
        raw_response=sql,
        candidate_sql=sql,
        generation_config=GenerationConfig(),
        generation_timestamp="2026-01-01T00:00:00+00:00",
        generation_duration_ms=1,
    )


def make_execution(task, candidate, rows, columns, status="SUCCEEDED", truncated=False):
    return ExecutionResult(
        execution_id=f"{candidate.candidate_id}.exec-test",
        task_id=task.task_id,
        candidate_id=candidate.candidate_id,
        status=status,
        failure=None,
        result_data=ResultData(
            columns=[ResultColumn(name=c, type="UNKNOWN") for c in columns],
            rows=[list(r) for r in rows],
            rows_returned=len(rows),
            truncated=truncated,
        )
        if status == "SUCCEEDED"
        else None,
        stdout="OK",
        stderr="",
        stdout_truncated=False,
        stderr_truncated=False,
        exit_code=0 if status == "SUCCEEDED" else 1,
        duration_ms=5,
        resource_limits={
            "timeout_seconds": 10.0,
            "memory_mb": 512,
            "cpus": 1.0,
            "pids_limit": 64,
            "max_result_rows": 10000,
            "max_result_bytes": 1048576,
            "max_stdout_bytes": 65536,
            "max_stderr_bytes": 65536,
        },
        resource_usage={"duration_ms": 5, "max_memory_mb": None, "output_bytes": 10},
        sandbox_image="test-image",
        sandbox_image_digest=None,
        sandbox_config_version="1.0",
        duckdb_version="1.5.5",
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
    )


def oracle_rows(task, tables=None):
    entry = get_oracle(task.template_id, task.template_version)
    expected = entry.fn(dict(task.requirements), tables if tables is not None else task.tables)
    return expected.columns, expected.rows


class SimBackend(ExecutionBackend):
    """Oracle-simulating backend with scripted deviations per label.

    - default: return oracle rows for the given tables (correct behavior)
    - ``perturb_labels``: labels returning oracle rows plus one bogus row
    - ``fail_labels``: labels raising BackendError (infra faults)
    - hidden rows regenerated through the real Phase 1 public API
    """

    def __init__(self, perturb_labels=(), fail_labels=()):
        self._perturb = set(perturb_labels)
        self._fail = set(fail_labels)
        self.calls = []

    def hidden_tables(self, task, hidden_seed):
        registry = load_builtin_registry()
        template = registry.get(task.template_id, task.template_version)
        hidden = generate_task(template, hidden_seed, dict(task.generation_metadata.config))
        return hidden.tables

    def run(self, task, candidate, tables, label):
        self.calls.append(label)
        if label in self._fail:
            raise BackendError(f"simulated infra fault on {label}")
        columns, rows = oracle_rows(task, tables if tables is not None else task.tables)
        rows = [list(r) for r in rows]
        if label in self._perturb:
            bogus = list(rows[0]) if rows else [None] * max(1, len(columns))
            bogus[0] = "PERTURBED" if not isinstance(bogus[0], bool) else (not bogus[0])
            rows = [*rows, bogus]
        return make_execution(task, candidate, rows, columns)

    def labels(self, prefix):
        return [c for c in self.calls if c.startswith(prefix)]
