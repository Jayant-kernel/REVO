"""Result comparison (Phase 4).

Compares oracle-expected rows against sandbox-observed rows using task
order semantics — never raw JSON strings. Rules:

- columns: names (case-insensitive by default) AND order are strict
- unordered results: multiset equality (tolerance-aware matching)
- ordered results: observed sequence must be sorted per the order keys
  (ties in any order) AND the multiset must match
- NULL equals NULL; booleans are type-strict; numerics (including numeric
  strings from Decimal serialization) compare with abs+relative tolerance
- differences are bounded to the first few rows
"""

from __future__ import annotations

import math
from itertools import pairwise
from typing import Any

from .models import ComparisonPolicy, ComparisonResult, ExpectedResult, OrderSpec, RowDifference

_MAX_DIFFS = 3


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def cells_equal(actual: Any, expected: Any, policy: ComparisonPolicy) -> bool:
    """One cell comparison following the documented NULL/numeric rules."""
    if expected is None or actual is None:
        return expected is None and actual is None
    if isinstance(expected, bool) or isinstance(actual, bool):
        return isinstance(expected, bool) and isinstance(actual, bool) and expected == actual
    num_a, num_e = _as_number(actual), _as_number(expected)
    if num_a is not None and num_e is not None:
        # Non-finite values (inf, or strings like "INFINITY") have no
        # meaningful tolerance band; identical spellings match, anything
        # else does not. This preserves reflexivity: equal inputs are equal.
        if not math.isfinite(num_a) or not math.isfinite(num_e):
            return str(actual) == str(expected)
        return abs(num_a - num_e) <= policy.float_abs_tol + policy.float_rel_tol * max(
            abs(num_a), abs(num_e)
        )
    return str(actual) == str(expected)


def rows_equal(actual: list[Any], expected: list[Any], policy: ComparisonPolicy) -> bool:
    return len(actual) == len(expected) and all(
        cells_equal(a, e, policy) for a, e in zip(actual, expected)
    )


def _three_way(actual: Any, expected: Any, direction: str) -> int:
    """Compare two key values with None-last semantics; -1/0/1."""
    if actual is None and expected is None:
        return 0
    if actual is None:
        return 1
    if expected is None:
        return -1
    num_a, num_e = _as_number(actual), _as_number(expected)
    if num_a is not None and num_e is not None:
        result = (num_a > num_e) - (num_a < num_e)
    else:
        result = (str(actual) > str(expected)) - (str(actual) < str(expected))
    return -result if direction == "desc" else result


def sequence_is_ordered(rows: list[list[Any]], columns: list[str], order: OrderSpec) -> bool:
    """Every consecutive pair is non-decreasing in the key space."""
    index = {c.lower(): i for i, c in enumerate(columns)}
    positions = []
    for name, direction in order.keys:
        pos = index.get(name.lower())
        if pos is None:
            return False
        positions.append((pos, direction))
    for first, second in pairwise(rows):
        for pos, direction in positions:
            outcome = _three_way(first[pos], second[pos], direction)
            if outcome < 0:
                break
            if outcome > 0:
                return False
        # outcome == 0 on all keys: tie, any order accepted
    return True


def _match_multiset(
    actual: list[list[Any]], expected: list[list[Any]], policy: ComparisonPolicy
) -> tuple[bool, list[RowDifference]]:
    """Greedy tolerance-aware multiset matching (deterministic, bounded)."""
    remaining = list(actual)
    differences: list[RowDifference] = []
    for i, exp_row in enumerate(expected):
        hit = next(
            (j for j, act_row in enumerate(remaining) if rows_equal(act_row, exp_row, policy)), None
        )
        if hit is None:
            differences.append(RowDifference(index=i, expected=list(exp_row), actual=[]))
            if len(differences) >= _MAX_DIFFS:
                break
        else:
            remaining.pop(hit)
    for extra in remaining[: max(0, _MAX_DIFFS - len(differences))]:
        differences.append(RowDifference(index=-1, expected=[], actual=list(extra)))
    return not differences, differences


def compare(
    expected: ExpectedResult,
    actual_columns: list[str],
    actual_rows: list[list[Any]],
    policy: ComparisonPolicy | None = None,
) -> ComparisonResult:
    """Compare expected vs observed results under task order semantics."""
    policy = policy or ComparisonPolicy()
    notes: list[str] = []

    if policy.column_names_case_sensitive:
        names_ok = actual_columns == expected.columns
    else:
        names_ok = [c.lower() for c in actual_columns] == [c.lower() for c in expected.columns]
    if not names_ok or len(actual_columns) != len(expected.columns):
        return ComparisonResult(
            match=False,
            expected_rows=len(expected.rows),
            actual_rows=len(actual_rows),
            expected_columns=list(expected.columns),
            actual_columns=list(actual_columns),
            order_spec=expected.order,
            policy=policy,
            notes=["column contract mismatch"],
        )

    width = len(expected.columns)
    raw_count = len(actual_rows)
    actual_rows = [list(r[:width]) for r in actual_rows if isinstance(r, list) and len(r) == width]
    if len(actual_rows) != raw_count:
        notes.append(f"dropped {raw_count - len(actual_rows)} malformed rows")

    if expected.order.type == "ordered":
        if not sequence_is_ordered(actual_rows, actual_columns, expected.order):
            return ComparisonResult(
                match=False,
                expected_rows=len(expected.rows),
                actual_rows=len(actual_rows),
                expected_columns=list(expected.columns),
                actual_columns=list(actual_columns),
                order_spec=expected.order,
                policy=policy,
                notes=["row order violates the task ORDER BY contract"],
            )
        notes.append("order verified; ties accepted in any order")

    match, differences = _match_multiset(actual_rows, expected.rows, policy)
    return ComparisonResult(
        match=match,
        expected_rows=len(expected.rows),
        actual_rows=len(actual_rows),
        expected_columns=list(expected.columns),
        actual_columns=list(actual_columns),
        order_spec=expected.order,
        policy=policy,
        differences=differences,
    )
