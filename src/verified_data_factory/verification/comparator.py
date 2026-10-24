"""Declared-type result comparison, exact arithmetic and complete bag matching."""
from __future__ import annotations

import math
import re
from collections import Counter, deque
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from itertools import pairwise
from typing import Any

from .models import ComparisonPolicy, ComparisonResult, ExpectedResult, OrderSpec, RowDifference

_MAX_DIFFS = 3
_INTEGER_TYPES = {"TINYINT", "SMALLINT", "INTEGER", "INT", "BIGINT", "HUGEINT", "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT", "UHUGEINT"}
_INTEGER_BITS = {
    "TINYINT": (8, True), "SMALLINT": (16, True), "INTEGER": (32, True),
    "INT": (32, True), "BIGINT": (64, True), "HUGEINT": (128, True),
    "UTINYINT": (8, False), "USMALLINT": (16, False), "UINTEGER": (32, False),
    "UBIGINT": (64, False), "UHUGEINT": (128, False),
}
_DECIMAL_TYPE = re.compile(r"(?:DECIMAL|NUMERIC)(?:\(([1-9][0-9]*)(?:,[ ]*([0-9]+))?\))?")
_TEXT_TYPE = re.compile(r"(?:VARCHAR|CHAR)(?:\([1-9][0-9]*\))?")


def _decimal_domain(dtype: str) -> tuple[int, int]:
    match = _DECIMAL_TYPE.fullmatch(dtype.upper().strip())
    if match is None:
        raise ValueError(f"unsupported declared type: {dtype}")
    precision = int(match.group(1) or 18)
    scale = int(match.group(2) or ("3" if match.group(1) is None else "0"))
    if not 1 <= precision <= 38 or not 0 <= scale <= precision:
        raise ValueError(f"unsupported declared type: {dtype}")
    return precision, scale


def _kind(dtype: str) -> str:
    dtype = dtype.upper().strip()
    if dtype in _INTEGER_TYPES:
        return "integer"
    decimal_match = _DECIMAL_TYPE.fullmatch(dtype)
    if decimal_match:
        _decimal_domain(dtype)
        return "decimal"
    if dtype in {"FLOAT", "REAL", "DOUBLE", "DOUBLE PRECISION"}:
        return "float"
    if dtype in {"TEXT", "STRING"} or _TEXT_TYPE.fullmatch(dtype):
        return "text"
    if dtype in {"BOOLEAN", "BOOL"}:
        return "boolean"
    if dtype == "DATE":
        return "date"
    if dtype == "TIMESTAMP":
        return "timestamp"
    if dtype == "TIME":
        return "time"
    raise ValueError(f"unsupported declared type: {dtype}")


def _native_type(values: list[Any]) -> str:
    """Scalar-helper compatibility uses Python types, never string spelling."""
    present = [v for v in values if v is not None]
    if not present:
        return "VARCHAR"
    if all(isinstance(v, str) for v in present):
        return "VARCHAR"
    if all(isinstance(v, bool) for v in present):
        return "BOOLEAN"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in present):
        return "BIGINT"
    if all(isinstance(v, int | float | Decimal) and not isinstance(v, bool) for v in present):
        return "DECIMAL" if any(isinstance(v, Decimal) for v in present) else "DOUBLE"
    if all(isinstance(v, datetime) for v in present):
        return "TIMESTAMP"
    if all(isinstance(v, date) for v in present):
        return "DATE"
    raise ValueError("scalar types disagree; declare the serialization type")


def _value(value: Any, kind: str, dtype: str = "") -> Any:
    if value is None:
        return None
    if kind == "text":
        if not isinstance(value, str):
            raise ValueError("text column requires text values")
        return value
    if kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError("boolean column requires booleans")
        return value
    if isinstance(value, bool):
        raise TypeError("boolean is not a numeric or temporal value")
    if kind in {"integer", "decimal"}:
        if not isinstance(value, int | float | Decimal | str):
            raise ValueError("invalid numeric representation")
        if kind == "integer" and isinstance(value, str) and not re.fullmatch(r"[+-]?[0-9]+", value.strip()):
            raise ValueError("invalid integer serialization")
        number = Decimal(value) if isinstance(value, int | Decimal) else Decimal(str(value))
        if not number.is_finite():
            raise ValueError("nonfinite exact numeric value")
        if kind == "integer":
            if number != number.to_integral_value():
                raise ValueError("fraction in integer column")
            integer = int(number)
            bits, signed = _INTEGER_BITS[dtype.upper().strip()]
            lower = -(2 ** (bits - 1)) if signed else 0
            upper = 2 ** (bits - int(signed)) - 1
            if not lower <= integer <= upper:
                raise ValueError("integer outside declared type range")
            return integer
        if dtype:
            precision, scale = _decimal_domain(dtype)
            # Tuple arithmetic never rounds under the ambient Decimal context.
            _, digits, exponent = number.as_tuple()
            assert isinstance(exponent, int)  # finite was checked above
            if any(digits):
                trailing = 0
                for digit in reversed(digits):
                    if digit:
                        break
                    trailing += 1
                if exponent + trailing < -scale:
                    raise ValueError("decimal exceeds declared scale")
                if len(digits) + exponent > precision - scale:
                    raise ValueError("decimal outside declared precision")
        return number
    if kind == "float":
        if not isinstance(value, int | float | Decimal | str):
            raise ValueError("invalid floating representation")
        return float(value)
    if kind == "date":
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if not isinstance(value, str):
            raise ValueError("invalid date representation")
        return date.fromisoformat(value)
    if kind == "timestamp":
        if isinstance(value, datetime):
            stamp = value
        elif isinstance(value, str):
            stamp = datetime.fromisoformat(value)
        else:
            raise ValueError("invalid timestamp representation")
        if stamp.tzinfo is not None:
            raise ValueError("timezone-aware timestamp unsupported")
        return stamp
    if kind == "time":
        if isinstance(value, time):
            clock = value
        elif isinstance(value, str):
            clock = time.fromisoformat(value)
        else:
            raise ValueError("invalid time representation")
        if clock.tzinfo is not None:
            raise ValueError("timezone-aware time unsupported")
        return clock
    raise ValueError("unknown column type")


def cells_equal(actual: Any, expected: Any, policy: ComparisonPolicy, column_type: str | None = None) -> bool:
    try:
        if column_type is not None:
            _kind(column_type)
        if actual is None or expected is None:
            return actual is None and expected is None
        if (column_type is None
                and all(isinstance(v, int | float | Decimal) and not isinstance(v, bool) for v in (actual, expected))
                and not all(isinstance(v, float) for v in (actual, expected))):
            if any(isinstance(v, Decimal) and not v.is_finite() for v in (actual, expected)):
                return False
            # Python numeric equality compares mixed native values exactly,
            # without rounding an integer or Decimal through float/str.
            return bool(actual == expected)
        dtype = column_type if column_type is not None else _native_type([actual, expected])
        kind = _kind(dtype)
        value_type = "" if column_type is None and kind == "decimal" else dtype
        a, e = _value(actual, kind, value_type), _value(expected, kind, value_type)
        if kind != "float":
            return bool(a == e)
        if math.isnan(a) or math.isnan(e):
            return math.isnan(a) and math.isnan(e)
        if not math.isfinite(a) or not math.isfinite(e):
            return bool(a == e)
        return bool(abs(a - e) <= policy.float_abs_tol + policy.float_rel_tol * max(abs(a), abs(e)))
    except (ValueError, TypeError, InvalidOperation, OverflowError):
        return False


def rows_equal(actual: list[Any], expected: list[Any], policy: ComparisonPolicy, column_types: list[str] | None = None) -> bool:
    if len(actual) != len(expected):
        return False
    types: list[str | None] = list(column_types) if column_types else [None] * len(expected)
    return len(types) == len(expected) and all(cells_equal(a, e, policy, dtype) for a, e, dtype in zip(actual, expected, types))


def _three_way(first: Any, second: Any, direction: str, dtype: str, nulls: str) -> int:
    if first is None or second is None:
        if first is second:
            return 0
        result = 1 if first is None else -1
        return -result if nulls == "first" else result
    kind = _kind(dtype)
    a, b = _value(first, kind, dtype), _value(second, kind, dtype)
    if kind == "float" and (math.isnan(a) or math.isnan(b)):
        result = int(math.isnan(a)) - int(math.isnan(b))
    else:
        result = (a > b) - (a < b)
    return -result if direction == "desc" else result


def sequence_is_ordered(rows: list[list[Any]], columns: list[str], order: OrderSpec, column_types: list[str] | None = None) -> bool:
    if not order.keys:
        return False
    try:
        types = column_types or [_native_type([row[i] for row in rows]) for i in range(len(columns))]
        if len(types) != len(columns):
            return False
        index = {name.lower(): i for i, name in enumerate(columns)}
        if len(index) != len(columns):
            return False
        for first, second in pairwise(rows):
            for name, direction in order.keys:
                position = index[name.lower()]
                outcome = _three_way(first[position], second[position], direction, types[position], order.nulls.get(name, "last"))
                if outcome < 0:
                    break
                if outcome > 0:
                    return False
        return all(name.lower() in index for name, _ in order.keys)
    except (ValueError, TypeError, KeyError, IndexError, InvalidOperation):
        return False


def _match_multiset(actual: list[list[Any]], expected: list[list[Any]], policy: ComparisonPolicy, types: list[str]) -> bool:
    if len(actual) != len(expected):
        return False
    kinds = [_kind(dtype) for dtype in types]
    if "float" not in kinds:
        def canonical(row: list[Any]) -> tuple[Any, ...]:
            return tuple(_value(v, kind, dtype) for v, kind, dtype in zip(row, kinds, types))
        return Counter(map(canonical, actual)) == Counter(map(canonical, expected))
    # Complete augmenting-path matching; unlike greedy matching, a row can be
    # reassigned when needed. Iterative traversal avoids a recursion-size limit.
    owners: dict[int, int] = {}
    assigned: dict[int, int] = {}
    for start in range(len(expected)):
        queue = deque([start])
        visited = {start}
        parents: dict[int, int] = {}
        endpoint: int | None = None
        while queue and endpoint is None:
            left = queue.popleft()
            for right, row in enumerate(actual):
                if right in parents or not rows_equal(row, expected[left], policy, types):
                    continue
                parents[right] = left
                if right not in owners:
                    endpoint = right
                    break
                next_left = owners[right]
                if next_left not in visited:
                    visited.add(next_left)
                    queue.append(next_left)
        if endpoint is None:
            return False
        while True:
            left = parents[endpoint]
            previous = assigned.get(left)
            owners[endpoint] = left
            assigned[left] = endpoint
            if previous is None:
                break
            endpoint = previous
    return True


def compare(expected: ExpectedResult, actual_columns: list[str], actual_rows: list[list[Any]], policy: ComparisonPolicy | None = None, *, column_types: list[str] | None = None) -> ComparisonResult:
    policy = policy or ComparisonPolicy()
    types = expected.column_types
    notes: list[str] = []
    names = actual_columns if policy.column_names_case_sensitive else [c.lower() for c in actual_columns]
    wanted = expected.columns if policy.column_names_case_sensitive else [c.lower() for c in expected.columns]
    if names != wanted:
        notes.append("column contract mismatch")
    elif len(set(names)) != len(names):
        notes.append("ambiguous duplicate output column names")
    elif len(types) != len(expected.columns):
        notes.append("declared column types required")
    elif any(not isinstance(row, list) or len(row) != len(types) for row in [*actual_rows, *expected.rows]):
        notes.append("malformed or wrong-width result rows")
    else:
        try:
            kinds = [_kind(dtype) for dtype in types]
            if expected.exact_column_types and (
                column_types is None
                or [dtype.upper().strip() for dtype in column_types]
                != [dtype.upper().strip() for dtype in types]
            ):
                raise ValueError("exact actual output type contract mismatch")
            if column_types is not None and (
                len(column_types) != len(types)
                or [_kind(dtype) for dtype in column_types] != kinds
            ):
                raise ValueError("actual output type contract mismatch")
            for row in [*actual_rows, *expected.rows]:
                for value, kind, dtype in zip(row, kinds, types):
                    _value(value, kind, dtype)
            if column_types is not None:
                for row in actual_rows:
                    for value, kind, dtype in zip(row, kinds, column_types):
                        _value(value, kind, dtype)
        except (ValueError, TypeError, InvalidOperation, OverflowError) as exc:
            notes.append(str(exc))
    if not notes and expected.order.type == "ordered" and not sequence_is_ordered(actual_rows, actual_columns, expected.order, types):
        notes.append("row order violates the task ORDER BY contract")
    matched = False
    if not notes:
        matched = _match_multiset(actual_rows, expected.rows, policy, types)
    differences = [] if matched or notes else [RowDifference(index=i, expected=row, actual=actual_rows[i] if i < len(actual_rows) else []) for i, row in enumerate(expected.rows[:_MAX_DIFFS])]
    return ComparisonResult(match=matched, expected_rows=len(expected.rows), actual_rows=len(actual_rows),
                            expected_columns=expected.columns, actual_columns=actual_columns,
                            order_spec=expected.order, policy=policy, differences=differences, notes=notes)
