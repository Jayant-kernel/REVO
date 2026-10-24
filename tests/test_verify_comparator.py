"""Comparator tests: exhaustive matrix over comparison semantics."""

import pytest

from verified_data_factory.verification.comparator import (
    cells_equal,
    compare,
    sequence_is_ordered,
)
from verified_data_factory.verification.models import ComparisonPolicy, ExpectedResult, OrderSpec

POLICY = ComparisonPolicy()


def _exp(columns, rows, order=None):
    types = []
    for index in range(len(columns)):
        value = next((r[index] for r in rows if r[index] is not None), None)
        types.append("BOOLEAN" if isinstance(value, bool) else "BIGINT" if isinstance(value, int)
                     else "DOUBLE" if isinstance(value, float) else "VARCHAR")
    return ExpectedResult(columns=columns, rows=rows, column_types=types, order=order or OrderSpec())


def test_identical_results_match():
    result = compare(
        _exp(["a", "b"], [[1, "x"], [2, "y"]]), ["a", "b"], [[1, "x"], [2, "y"]], POLICY
    )
    assert result.match
    assert result.expected_rows == 2 and result.actual_rows == 2


def test_unordered_row_permutation_matches():
    result = compare(_exp(["a"], [[1], [2], [3]]), ["a"], [[3], [1], [2]], POLICY)
    assert result.match


def test_missing_and_extra_rows_fail_with_bounded_evidence():
    result = compare(_exp(["a"], [[1], [2]]), ["a"], [[1], [3]], POLICY)
    assert not result.match
    assert len(result.differences) <= 3
    assert result.expected_rows == 2 and result.actual_rows == 2


def test_column_name_mismatch_fails():
    result = compare(
        _exp(["customer_id", "total"], [[1, 2.0]]), ["customer_id", "revenue"], [[1, 2.0]], POLICY
    )
    assert not result.match


def test_column_order_is_strict():
    result = compare(_exp(["a", "b"], [[1, 2]]), ["b", "a"], [[2, 1]], POLICY)
    assert not result.match


def test_column_names_case_insensitive_by_default():
    result = compare(_exp(["Customer_ID"], [[1]]), ["customer_id"], [[1]], POLICY)
    assert result.match


def test_null_semantics():
    assert cells_equal(None, None, POLICY)
    assert not cells_equal(None, 0, POLICY)
    assert not cells_equal(None, "", POLICY)
    result = compare(_exp(["a"], [[None], [1]]), ["a"], [[1], [None]], POLICY)
    assert result.match


def test_booleans_are_type_strict():
    assert cells_equal(True, True, POLICY)
    assert not cells_equal(True, 1, POLICY)
    assert not cells_equal(1, True, POLICY)
    assert not cells_equal(False, 0, POLICY)


def test_integers_and_floats():
    assert cells_equal(3, 3.0, POLICY)
    assert not cells_equal(3, 4, POLICY)


def test_numeric_strings_from_decimal_serialization():
    assert cells_equal("10.50", 10.5, POLICY, "DECIMAL")
    assert cells_equal("7", 7.0, POLICY, "DECIMAL")
    assert not cells_equal("2025-01-01", 20250101, POLICY)


def test_float_tolerance_boundaries():
    tight = ComparisonPolicy(float_abs_tol=1e-9, float_rel_tol=0.0)
    assert cells_equal(1.0, 1.0 + 5e-10, tight)
    assert not cells_equal(1.0, 1.0 + 5e-9, tight)
    assert not cells_equal(100.0, 101.0, tight)
    loose = ComparisonPolicy(float_abs_tol=0.0, float_rel_tol=1e-7)
    assert cells_equal(1e6, 1e6 + 0.05, loose)
    assert not cells_equal(1e6, 1e6 + 0.5, loose)


def test_huge_tolerance_rejected_by_config():
    # Config validation cannot express "too huge"; the suite pins sane values.
    assert ComparisonPolicy().float_abs_tol <= 1e-6
    assert ComparisonPolicy().float_rel_tol <= 1e-4


def test_dates_and_timestamps_as_strings():
    assert cells_equal("2025-01-01", "2025-01-01", POLICY)
    assert not cells_equal("2025-01-01", "2025-01-02", POLICY)
    assert cells_equal("2025-01-01 10:00:00", "2025-01-01 10:00:00", POLICY)


def test_empty_results_match_with_columns():
    result = compare(_exp(["a", "b"], []), ["a", "b"], [], POLICY)
    assert result.match


def test_duplicate_rows_count():
    result = compare(_exp(["a"], [[1], [1]]), ["a"], [[1]], POLICY)
    assert not result.match


def test_ordered_strict_passes():
    order = OrderSpec(type="ordered", keys=[("customer_id", "asc")])
    result = compare(_exp(["customer_id"], [[1], [2]], order), ["customer_id"], [[1], [2]], POLICY)
    assert result.match


def test_ordered_violation_fails():
    order = OrderSpec(type="ordered", keys=[("customer_id", "asc")])
    result = compare(_exp(["customer_id"], [[1], [2]], order), ["customer_id"], [[2], [1]], POLICY)
    assert not result.match
    assert "ORDER BY" in result.notes[0]


def test_ordered_desc_with_ties_accepted():
    order = OrderSpec(type="ordered", keys=[("revenue", "desc")])
    exp = _exp(["id", "revenue"], [[1, 30.0], [2, 30.0], [3, 10.0]], order)
    assert compare(exp, ["id", "revenue"], [[2, 30.0], [1, 30.0], [3, 10.0]], POLICY).match
    assert not compare(exp, ["id", "revenue"], [[3, 10.0], [1, 30.0], [2, 30.0]], POLICY).match


def test_sequence_is_ordered_multi_key():
    asc2 = OrderSpec(type="ordered", keys=[("x", "asc"), ("y", "asc")])
    assert sequence_is_ordered([[1, "b"], [1, "c"], [2, "a"]], ["x", "y"], asc2)
    assert not sequence_is_ordered([[1, "c"], [1, "b"]], ["x", "y"], asc2)
    assert sequence_is_ordered(
        [[1], [None]], ["x"], OrderSpec(type="ordered", keys=[("x", "asc")])
    )  # NULLS LAST
    assert sequence_is_ordered(
        [[1], [None]], ["x"], OrderSpec(type="ordered", keys=[("x", "desc")])
    )
    assert not sequence_is_ordered(
        [[None], [1]], ["x"], OrderSpec(type="ordered", keys=[("x", "asc")])
    )


def test_unknown_order_column_fails_closed():
    order = OrderSpec(type="ordered", keys=[("nope", "asc")])
    result = compare(_exp(["a"], [[1]], order), ["a"], [[1]], POLICY)
    assert not result.match


@pytest.mark.parametrize("a,e,expected", [(None, None, True), (0, None, False), ("x", "x", True)])
def test_cells_parametrized(a, e, expected):
    assert cells_equal(a, e, POLICY) is expected


def test_nonfinite_values_reflexive_not_tolerance_compared():
    # Regression: identical non-finite spellings must match (Phase 6 gate
    # caught cells_equal("INFINITY", "INFINITY") returning False via NaN).
    assert cells_equal("INFINITY", "INFINITY", POLICY) is True
    assert cells_equal(float("inf"), float("inf"), POLICY) is True
    assert cells_equal("INFINITY", "1e999", POLICY) is False
    assert cells_equal(float("inf"), 1.0, POLICY) is False
