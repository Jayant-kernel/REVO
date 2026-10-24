"""Model-free reproductions of the six confirmed result-comparison defects."""
import ast
import hashlib
from decimal import Decimal
from itertools import permutations
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from verified_data_factory.verification.comparator import cells_equal, compare
from verified_data_factory.verification.models import ComparisonPolicy, ExpectedResult, OrderSpec


def expected(rows, dtype="DOUBLE", ordered=False):
    return ExpectedResult(columns=["v"], rows=rows, column_types=[dtype],
                          order=OrderSpec(type="ordered", keys=[("v", "asc")]) if ordered else OrderSpec())


def test_large_integers_differing_by_one_are_not_equal():
    assert not cells_equal(2**53, 2**53 + 1, ComparisonPolicy(float_abs_tol=0, float_rel_tol=0))


def test_integer_comparison_never_uses_relative_float_tolerance():
    assert not cells_equal(1_000_000_000, 1_000_000_001, ComparisonPolicy())


def test_numeric_looking_text_retains_identity():
    assert not cells_equal("001", "1", ComparisonPolicy())


def test_numeric_looking_text_uses_text_order():
    assert compare(expected([["10"], ["2"]], "VARCHAR", True), ["v"], [["10"], ["2"]]).match


def test_wrong_width_rows_fail_closed_even_for_empty_expected_result():
    assert not compare(expected([], "INTEGER"), ["v"], [[1, 2]]).match


def test_tolerant_matching_finds_a_complete_matching():
    policy = ComparisonPolicy(float_abs_tol=0.06, float_rel_tol=0)
    for rows in ([[0.05], [0.15]], [[0.15], [0.05]]):
        assert compare(expected([[0.1], [0.0]]), ["v"], rows, policy).match


def test_decimal_comparison_is_exact():
    assert not cells_equal(Decimal("1000000000.00"), Decimal("1000000000.01"), ComparisonPolicy())


@given(st.lists(st.floats(-1, 1, allow_nan=False, allow_infinity=False), min_size=1, max_size=4))
def test_unordered_tolerant_comparison_is_permutation_invariant(values):
    exp = expected([[float(v)] for v in values])
    actual = [[float(v) + 0.01] for v in values]
    policy = ComparisonPolicy(float_abs_tol=0.1, float_rel_tol=0)
    outcomes = {compare(exp, ["v"], list(permutation), policy).match for permutation in permutations(actual)}
    assert outcomes == {True}


@pytest.mark.parametrize("rows", [[], [[None]], [[None], [None]]])
def test_null_and_empty_results_have_explicit_column_types(rows):
    assert compare(expected(rows, "INTEGER"), ["v"], rows).match


@pytest.mark.parametrize("dtype,rows", [("UNKNOWN", [[1]]), ("VARCHAR", [[1]]), ("INTEGER", [[1.5]])])
def test_unknown_or_invalid_declared_values_fail_closed(dtype, rows):
    assert not compare(expected(rows, dtype), ["v"], rows).match


def test_missing_column_type_contract_fails_closed():
    assert not compare(ExpectedResult(columns=["v"], rows=[[1]]), ["v"], [[1]]).match


def test_decimal_strings_use_declared_numeric_type_not_text_guessing():
    assert cells_equal("10.50", Decimal("10.5"), ComparisonPolicy(), "DECIMAL(18,2)")
    assert not cells_equal("1000000000.01", Decimal("1000000000.00"), ComparisonPolicy(), "DECIMAL(18,2)")


def test_nulls_first_is_an_explicit_order_contract():
    exp = expected([[None], [1]], "INTEGER", True)
    exp = exp.model_copy(update={"order": OrderSpec(type="ordered", keys=[("v", "asc")], nulls={"v": "first"})})
    assert compare(exp, ["v"], [[None], [1]]).match
    assert not compare(exp, ["v"], [[1], [None]]).match


def test_declared_types_cannot_be_overridden_by_execution_metadata():
    assert not compare(expected([["001"]], "VARCHAR"), ["v"], [[1]], column_types=["BIGINT"]).match


def test_all_production_comparison_calls_pass_declared_types():
    checked = 0
    for path in Path("src/verified_data_factory").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "compare" and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "compare_mod"):
                assert any(keyword.arg == "column_types" for keyword in node.keywords), str(path)
                checked += 1
    assert checked == 7


def test_duplicate_and_unknown_order_columns_fail_closed():
    duplicate = ExpectedResult(columns=["v", "v"], column_types=["INTEGER", "INTEGER"], rows=[[1, 2]])
    assert not compare(duplicate, ["v", "v"], [[1, 2]]).match
    unknown = expected([], "INTEGER", True).model_copy(update={"order": OrderSpec(type="ordered", keys=[("missing", "asc")])})
    assert not compare(unknown, ["v"], []).match


def test_verification_identity_cannot_reuse_the_old_comparator_identity():
    from verified_data_factory.verification.verifier import build_verification_id
    old_digest = hashlib.sha256(b"task|candidate|execution|config|1").hexdigest()[:12]
    assert build_verification_id("task", "candidate", "execution", "config", 1) != f"candidate.verify-{old_digest}"
