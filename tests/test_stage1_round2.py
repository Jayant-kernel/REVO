"""Cold-challenger regression witnesses for the bounded Stage 1 retry."""
from decimal import Decimal

import pytest

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.comparator import cells_equal, compare
from verified_data_factory.verification.models import ComparisonPolicy
from verified_data_factory.verification.oracle_registry import get_oracle


@pytest.mark.parametrize("reverse", [False, True])
def test_ranked_v1_refuses_unprovable_required_date_order(reverse):
    task = generate_task(load_builtin_registry().get("sql.windows.ranked", 1), 601)
    tables = {"orders": [
        {"customer_id": 1, "order_id": 1, "order_date": "2025-01-01", "amount": 3.0, "status": "completed"},
        {"customer_id": 1, "order_id": 2, "order_date": "2025-01-02", "amount": 4.0, "status": "completed"},
    ]}
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, tables)
    rows = list(reversed(expected.rows)) if reverse else expected.rows
    result = compare(expected, expected.columns, rows, column_types=expected.column_types)
    assert not result.match
    assert "row order violates the task ORDER BY contract" in result.notes
    assert expected.order.keys == [("customer_id", "asc"), ("order_date", "asc")]
    assert "order_date" not in expected.columns


def test_ranked_v2_remains_usable_with_projected_date():
    task = generate_task(load_builtin_registry().get("sql.windows.ranked", 2), 601)
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, task.tables)
    assert "order_date" in expected.columns
    assert compare(expected, expected.columns, expected.rows, column_types=expected.column_types).match


@pytest.mark.parametrize("actual,expected", [
    (float(2**53), 2**53 + 1),
    (2**53 + 1, float(2**53)),
    (Decimal("0.1"), 0.1),
    (0.1, Decimal("0.1")),
])
@pytest.mark.parametrize("tolerance", [0.0, 1.0])
def test_native_mixed_exact_numbers_never_acquire_float_tolerance(actual, expected, tolerance):
    policy = ComparisonPolicy(float_abs_tol=tolerance, float_rel_tol=tolerance)
    assert not cells_equal(actual, expected, policy)


@pytest.mark.parametrize("actual,expected", [(3, 3.0), (3.0, 3),
                                           (Decimal.from_float(0.1), 0.1),
                                           (0.1, Decimal.from_float(0.1))])
def test_lossless_native_mixed_numeric_equality(actual, expected):
    assert cells_equal(actual, expected, ComparisonPolicy())


def test_explicit_double_keeps_declared_floating_policy():
    policy = ComparisonPolicy(float_abs_tol=0.0, float_rel_tol=0.0)
    assert cells_equal(float(2**53), 2**53 + 1, policy, "DOUBLE")
    assert cells_equal(Decimal("0.1"), 0.1, policy, "DOUBLE")


@pytest.mark.parametrize("dtype", ["JSON", "DECIMAL(2,3)", "DECIMAL(39,0)", ""])
def test_explicit_type_validation_precedes_null_equality(dtype):
    assert not cells_equal(None, None, ComparisonPolicy(), dtype)


def test_supported_and_untyped_null_equality_survives():
    assert cells_equal(None, None, ComparisonPolicy())
    assert cells_equal(None, None, ComparisonPolicy(), "DECIMAL(2,1)")
    assert not cells_equal(None, 1, ComparisonPolicy(), "INTEGER")
