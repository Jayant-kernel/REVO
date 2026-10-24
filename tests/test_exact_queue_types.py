"""Opt-in exact SQL types, preserving legacy witness shape and kind comparison."""
import json

import pytest

from scripts.engineering_receipt_artifacts import ArtifactWriter
from tests.verify_testkit import make_candidate
from verified_data_factory.sandbox import SandboxExecutor, load_config
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification import verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.comparator import compare
from verified_data_factory.verification.models import ExpectedResult, OracleOutcome
from verified_data_factory.verification.qualification import queue_batches_profile as queue
from verified_data_factory.verification.receipt_models import SQLWitness
from verified_data_factory.verification.receipt_validation import DetailValidator

pytest_plugins = ["tests.test_stage2_receipt_producer"]


@pytest.mark.parametrize("rows", [[], [[None]], [[1], [2], [3]], [[-(2**31)], [2**31-1]]])
@pytest.mark.parametrize("wanted,actual", [("INTEGER", "BIGINT"), ("BIGINT", "INTEGER")])
def test_exact_width_is_opt_in_even_for_empty_and_nullable(rows, wanted, actual):
    legacy = ExpectedResult(columns=["v"], column_types=[wanted], rows=rows)
    assert compare(legacy, ["v"], rows, column_types=[actual]).match
    exact = legacy.model_copy(update={"exact_column_types": True})
    assert not compare(exact, ["v"], rows, column_types=[actual]).match
    assert not compare(exact, ["v"], rows).match
    assert compare(exact, ["v"], rows, column_types=[wanted.lower()]).match
    assert ExpectedResult.model_validate_json(exact.model_dump_json()) == exact


@pytest.mark.parametrize("dtype,bits", [("INTEGER", 32), ("BIGINT", 64)])
def test_exact_does_not_bypass_signed_bounds_or_value_validation(dtype, bits):
    for value, valid in [(-(2**(bits-1)), True), (2**(bits-1)-1, True),
                         (-(2**(bits-1))-1, False), (2**(bits-1), False), (True, False)]:
        expected = ExpectedResult(columns=["v"], column_types=[dtype], rows=[[value]],
                                  exact_column_types=True)
        assert compare(expected, ["v"], [[value]], column_types=[dtype]).match is valid


def test_old_witness_and_oracle_json_canonical_shape_is_unchanged():
    old = {"columns": ["v"], "column_types": ["BIGINT"], "rows": [[1]],
           "order": {"type": "unordered", "keys": [], "nulls": {}}}
    expected = ExpectedResult.model_validate(old)
    assert expected.model_dump(mode="json") == old
    assert json.loads(expected.model_dump_json()) == old
    oracle = OracleOutcome(ok=True, expected=expected)
    assert oracle.model_dump(mode="json")["expected"] == old
    assert json.loads(oracle.model_dump_json())["expected"] == old
    assert compare(expected, ["v"], [[1]], column_types=["INTEGER"]).match


def test_actual_integer_cast_runtime_fails_not_false_strong():
    task = generate_task(load_builtin_registry().get(queue.CONTRACT, 1), 94001)
    sql = queue.failures(queue.REFERENCE)["int_batch"]
    candidate = make_candidate(task, sql)
    config = load_config("configs/sandbox_production.yaml")
    execution = SandboxExecutor(config).execute(task, candidate)
    assert execution.status == "SUCCEEDED"
    assert [c.type for c in execution.result_data.columns] == ["INTEGER", "INTEGER"]
    result = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(config))
    assert result.verdict == "FAIL", result.model_dump_json()
    assert result.verification_strength != "STRONG"
    assert result.failure_code == "RESULT_MISMATCH"


def test_retained_integer_cast_is_semantic_kill_and_replays(producer_root):
    writer = ArtifactWriter(producer_root, "exact-queue-types", queue.CONTRACT, 1,
                            ["pyproject.toml"])
    fixture = writer.fixture(queue.rich_fixture())
    assert fixture.expected.exact_column_types
    correct, wrong = writer.sql_many(
        [queue.REFERENCE, queue.failures(queue.REFERENCE)["int_batch"]], fixture)
    assert correct.outcome == "MATCH"
    assert wrong.outcome == "KILLED_WRONG_ANSWER"
    assert wrong.comparison.notes == ["exact actual output type contract mismatch"]
    validator = DetailValidator(producer_root, writer.task, public_behavior_map(writer.task),
                                writer.sources, writer.thresholds)
    for witness in (correct, wrong):
        retained = SQLWitness.model_validate_json(witness.model_dump_json())
        assert retained.fixture.expected.exact_column_types
        validator.sql(retained)
    assert validator.run_count == 2


@pytest.mark.parametrize("form", ["bigint_cast", "unsupported_native"])
def test_unattested_correct_native_is_not_strong(form):
    task = generate_task(load_builtin_registry().get(queue.CONTRACT, 1), 94001)
    sql = (queue.failures(queue.REFERENCE)["int_batch"].replace("AS INTEGER)", "AS BIGINT)")
           if form == "bigint_cast" else queue.REFERENCE.replace("NTILE(3)", "NTILE(1+2)"))
    candidate = make_candidate(task, sql)
    config = load_config("configs/sandbox_production.yaml")
    execution = SandboxExecutor(config).execute(task, candidate)
    assert execution.status == "SUCCEEDED"
    result = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(config))
    if form == "unsupported_native":
        assert result.verdict == "INCONCLUSIVE", result.model_dump_json()
    else:
        assert result.verdict == "PASS", result.model_dump_json()
        assert not result.mutation.coverage_complete
    assert result.verification_strength != "STRONG"
