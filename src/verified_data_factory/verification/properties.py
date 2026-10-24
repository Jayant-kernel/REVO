"""Property checks (Phase 4).

Properties are justified per task family (never generic):
- ROW_ORDER_INVARIANCE: outputs are fully ordered, so shuffling source rows
  must not change the oracle-verified result (all families).
- DUPLICATE_INVARIANCE: exact duplicate events must not change dedup/funnel
  results (first-occurrence chaining / latest-wins semantics).
- IRRELEVANT_NONQUALIFYING_EVENT: a non-purchase event must not change
  retention flags.

Unknown families raise instead of receiving silent generic properties.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.task_engine.models import TaskInstance

from . import comparator as compare_mod
from .backend import ExecutionBackend
from .errors import BackendError, OracleError
from .models import ComparisonPolicy, ExpectedResult, PropertyOutcome, PropertyResult

OracleFn = Callable[[Any, Any], ExpectedResult]


class PropertyContext:
    """Everything a property check may consume (no candidate internals)."""

    __slots__ = ("backend", "candidate", "expected_fn", "policy", "seed", "tables", "task")

    def __init__(
        self,
        task: TaskInstance,
        candidate: CandidateSolution,
        tables: dict[str, list[dict[str, Any]]],
        expected_fn: OracleFn,
        backend: ExecutionBackend,
        policy: ComparisonPolicy,
        seed: int,
    ) -> None:
        self.task = task
        self.candidate = candidate
        self.tables = tables
        self.expected_fn = expected_fn
        self.backend = backend
        self.policy = policy
        self.seed = seed


def _expected(ctx: PropertyContext, tables: dict[str, list[dict[str, Any]]]) -> ExpectedResult:
    return ctx.expected_fn(dict(ctx.task.requirements), tables)


def _run_and_compare(
    ctx: PropertyContext, tables: dict[str, list[dict[str, Any]]], label: str
) -> tuple[bool, str]:
    execution = ctx.backend.run(ctx.task, ctx.candidate, tables, label)
    if execution.status != "SUCCEEDED" or execution.result_data is None:
        return False, f"property execution {execution.status}"
    expected = _expected(ctx, tables)
    comparison = compare_mod.compare(
        expected,
        [c.name for c in execution.result_data.columns],
        execution.result_data.rows,
        ctx.policy,
        column_types=[c.type for c in execution.result_data.columns],
    )
    if comparison.match:
        return True, ""
    return False, f"expected {comparison.expected_rows} rows, got {comparison.actual_rows}"


def check_row_order_invariance(ctx: PropertyContext) -> PropertyOutcome:
    rng = random.Random(ctx.seed)
    shuffled = {name: list(rows) for name, rows in ctx.tables.items()}
    for rows in shuffled.values():
        rng.shuffle(rows)
    passed, detail = _run_and_compare(ctx, shuffled, "property:row_order_invariance")
    return PropertyOutcome(
        property_id="ROW_ORDER_INVARIANCE", applicable=True, passed=passed, detail=detail
    )


def _with_new_pk(rows: list[dict[str, Any]], pk: str) -> int:
    return max((r[pk] for r in rows if isinstance(r.get(pk), int)), default=0) + 1


def check_duplicate_invariance(ctx: PropertyContext) -> PropertyOutcome:
    if (ctx.task.template_id, ctx.task.template_version) == ("sql.funnel.saas_activation_payment", 2):
        from .metamorphic import contract_relation_tables
        tables, reason = contract_relation_tables(ctx.task, ctx.tables, "SAAS_LATER_PAYMENT")
        if tables is None:
            return PropertyOutcome(property_id="LATER_PAYMENT_INVARIANCE", applicable=False, passed=False, detail=reason)
        passed, detail = _run_and_compare(ctx, tables, "property:later_payment_invariance")
        return PropertyOutcome(property_id="LATER_PAYMENT_INVARIANCE", applicable=True, passed=passed, detail=detail or reason)
    rows = ctx.tables.get("events", [])
    if not rows:
        return PropertyOutcome(
            property_id="DUPLICATE_INVARIANCE",
            applicable=False,
            passed=False,
            detail="no events table",
        )
    dup = dict(rows[0])
    dup["event_id"] = _with_new_pk(rows, "event_id")
    tables = {**ctx.tables, "events": [*rows, dup]}
    passed, detail = _run_and_compare(ctx, tables, "property:duplicate_invariance")
    return PropertyOutcome(
        property_id="DUPLICATE_INVARIANCE", applicable=True, passed=passed, detail=detail
    )


def check_irrelevant_nonqualifying_event(ctx: PropertyContext) -> PropertyOutcome:
    rows = ctx.tables.get("events", [])
    customers = ctx.tables.get("customers", [])
    if not rows or not customers:
        return PropertyOutcome(
            property_id="IRRELEVANT_NONQUALIFYING_EVENT",
            applicable=False,
            passed=False,
            detail="missing tables",
        )
    extra = {
        "event_id": _with_new_pk(rows, "event_id"),
        "customer_id": customers[0]["customer_id"],
        "event_type": "view",
        "event_time": "2025-02-15 12:00:00",
    }
    tables = {**ctx.tables, "events": [*rows, extra]}
    passed, detail = _run_and_compare(ctx, tables, "property:irrelevant_event")
    return PropertyOutcome(
        property_id="IRRELEVANT_NONQUALIFYING_EVENT", applicable=True, passed=passed, detail=detail
    )


PropertyFn = Callable[[PropertyContext], PropertyOutcome]

PROPERTY_REGISTRY: dict[str, list[PropertyFn]] = {
    "simple_joins": [check_row_order_invariance],
    "multi_joins": [check_row_order_invariance],
    "aggregation": [check_row_order_invariance],
    "cte": [check_row_order_invariance],
    "subqueries": [check_row_order_invariance],
    "window_functions": [check_row_order_invariance],
    "temporal": [check_row_order_invariance],
    "deduplication": [check_row_order_invariance, check_duplicate_invariance],
    "retention": [check_row_order_invariance, check_irrelevant_nonqualifying_event],
    "funnel": [check_row_order_invariance, check_duplicate_invariance],
}

PROPERTY_VERSION = 1


def properties_for_family(family: str) -> list[PropertyFn]:
    try:
        return PROPERTY_REGISTRY[family]
    except KeyError as exc:
        raise OracleError(f"no properties registered for family {family!r}") from exc


def run_property_checks(ctx: PropertyContext) -> PropertyResult:
    outcomes: list[PropertyOutcome] = []
    for fn in properties_for_family(ctx.task.family):
        try:
            outcome = fn(ctx)
        except BackendError:
            raise
        except Exception as exc:  # noqa: BLE001 — property faults are data
            outcome = PropertyOutcome(
                property_id=getattr(fn, "__name__", "unknown").upper(),
                applicable=True,
                passed=False,
                detail=f"property error: {exc}"[:300],
            )
        outcomes.append(outcome)
    applicable = [o for o in outcomes if o.applicable]
    return PropertyResult(
        applicable=len(applicable),
        passed=sum(1 for o in applicable if o.passed),
        failed=sum(1 for o in applicable if not o.passed),
        outcomes=outcomes,
    )
