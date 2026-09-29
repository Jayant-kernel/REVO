"""Metamorphic relations (Phase 4).

Each relation transforms the fixture, re-executes the SAME candidate, and
checks a known A-vs-B relation — no oracle involved at this stage (oracle
comparison is a separate pipeline stage). Relations are family-justified:

- ROW_PERMUTATION (all): shuffled inputs, same semantic result.
- ADD_IRRELEVANT_CUSTOMER (join/cte/subquery/window families): an entity
  with no orders contributes no rows under INNER-JOIN exclusion.
- ADD_DUPLICATE_EVENT (dedup/funnel/retention): duplicates cannot move
  latest-wins / first-occurrence / any-qualifying outcomes.
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
from .models import ComparisonPolicy, ExpectedResult, MetamorphicOutcome, MetamorphicResult


class MetamorphicContext:
    """Inputs for one relation check (candidate result A + transform)."""

    __slots__ = (
        "backend",
        "candidate",
        "candidate_columns",
        "candidate_rows",
        "order",
        "policy",
        "seed",
        "tables",
        "task",
    )

    def __init__(
        self,
        task: TaskInstance,
        candidate: CandidateSolution,
        tables: dict[str, list[dict[str, Any]]],
        candidate_columns: list[str],
        candidate_rows: list[list[Any]],
        order: Any,
        backend: ExecutionBackend,
        policy: ComparisonPolicy,
        seed: int,
    ) -> None:
        self.task = task
        self.candidate = candidate
        self.tables = tables
        self.candidate_columns = candidate_columns
        self.candidate_rows = candidate_rows
        self.order = order
        self.backend = backend
        self.policy = policy
        self.seed = seed


def _compare_against_original(
    ctx: MetamorphicContext, tables: dict[str, list[dict[str, Any]]], label: str
) -> tuple[bool, str]:
    execution = ctx.backend.run(ctx.task, ctx.candidate, tables, label)
    if execution.status != "SUCCEEDED" or execution.result_data is None:
        return False, f"metamorphic execution {execution.status}"
    expected = ExpectedResult(
        columns=ctx.candidate_columns, rows=ctx.candidate_rows, order=ctx.order
    )
    comparison = compare_mod.compare(
        expected,
        [c.name for c in execution.result_data.columns],
        execution.result_data.rows,
        ctx.policy,
    )
    if comparison.match:
        return True, ""
    return False, f"expected {comparison.expected_rows} rows, got {comparison.actual_rows}"


def relate_row_permutation(ctx: MetamorphicContext) -> MetamorphicOutcome:
    rng = random.Random(ctx.seed)
    shuffled = {name: list(rows) for name, rows in ctx.tables.items()}
    for rows in shuffled.values():
        rng.shuffle(rows)
    passed, detail = _compare_against_original(ctx, shuffled, "metamorphic:row_permutation")
    return MetamorphicOutcome(
        relation_id="ROW_PERMUTATION", applicable=True, passed=passed, detail=detail
    )


def relate_add_irrelevant_customer(ctx: MetamorphicContext) -> MetamorphicOutcome:
    customers = ctx.tables.get("customers")
    if not customers:
        return MetamorphicOutcome(
            relation_id="ADD_IRRELEVANT_CUSTOMER",
            applicable=False,
            passed=False,
            detail="no customers table",
        )
    ghost_id = max(c["customer_id"] for c in customers) + 1
    ghost = {
        "customer_id": ghost_id,
        "name": "Meta Ghost",
        "country": "XX",
        "signup_date": "2024-06-01",
    }
    tables = {**ctx.tables, "customers": [*customers, ghost]}
    passed, detail = _compare_against_original(ctx, tables, "metamorphic:add_irrelevant_customer")
    return MetamorphicOutcome(
        relation_id="ADD_IRRELEVANT_CUSTOMER", applicable=True, passed=passed, detail=detail
    )


def relate_add_duplicate_event(ctx: MetamorphicContext) -> MetamorphicOutcome:
    rows = ctx.tables.get("events", [])
    if not rows:
        return MetamorphicOutcome(
            relation_id="ADD_DUPLICATE_EVENT",
            applicable=False,
            passed=False,
            detail="no events table",
        )
    dup = dict(rows[0])
    dup["event_id"] = max(r["event_id"] for r in rows if isinstance(r.get("event_id"), int)) + 1
    tables = {**ctx.tables, "events": [*rows, dup]}
    passed, detail = _compare_against_original(ctx, tables, "metamorphic:add_duplicate_event")
    return MetamorphicOutcome(
        relation_id="ADD_DUPLICATE_EVENT", applicable=True, passed=passed, detail=detail
    )


RelationFn = Callable[[MetamorphicContext], MetamorphicOutcome]

RELATION_REGISTRY: dict[str, list[RelationFn]] = {
    "simple_joins": [relate_row_permutation, relate_add_irrelevant_customer],
    "multi_joins": [relate_row_permutation, relate_add_irrelevant_customer],
    "aggregation": [relate_row_permutation],
    "cte": [relate_row_permutation, relate_add_irrelevant_customer],
    "subqueries": [relate_row_permutation, relate_add_irrelevant_customer],
    "window_functions": [relate_row_permutation, relate_add_irrelevant_customer],
    "temporal": [relate_row_permutation],
    "deduplication": [relate_row_permutation, relate_add_duplicate_event],
    "retention": [relate_row_permutation, relate_add_duplicate_event],
    "funnel": [relate_row_permutation, relate_add_duplicate_event],
}

RELATION_VERSION = 1


def relations_for_family(family: str) -> list[RelationFn]:
    try:
        return RELATION_REGISTRY[family]
    except KeyError as exc:
        raise OracleError(f"no metamorphic relations registered for family {family!r}") from exc


def run_metamorphic_checks(ctx: MetamorphicContext) -> MetamorphicResult:
    outcomes: list[MetamorphicOutcome] = []
    for fn in relations_for_family(ctx.task.family):
        try:
            outcome = fn(ctx)
        except BackendError:
            raise
        except Exception as exc:  # noqa: BLE001 — relation faults are data
            outcome = MetamorphicOutcome(
                relation_id=getattr(fn, "__name__", "unknown").upper(),
                applicable=True,
                passed=False,
                detail=f"relation error: {exc}"[:300],
            )
        outcomes.append(outcome)
    applicable = [o for o in outcomes if o.applicable]
    return MetamorphicResult(
        applicable=len(applicable),
        passed=sum(1 for o in applicable if o.passed),
        failed=sum(1 for o in applicable if not o.passed),
        outcomes=outcomes,
    )
