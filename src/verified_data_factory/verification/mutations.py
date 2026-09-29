"""Mutation testing (Phase 4).

Controlled incorrect variants of the CANDIDATE's SQL (never the task spec)
are executed and verified. A strong suite rejects (kills) them; survivors
are recorded evidence of suite weakness — never candidate guilt.

- ``mutation_score = caught / (caught + survived)``; inconclusive mutants
  (sandbox infra faults) are excluded, never counted as caught.
- Zero applicable operators → score ``None`` (NOT_APPLICABLE), never a
  manufactured 100%.
- Operators are family-aware text transforms chosen to be killable on real
  fixtures (weaker predicates, flipped directions, wrong keys/columns).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.task_engine.models import TaskInstance

from . import comparator as compare_mod
from .backend import ExecutionBackend
from .models import ComparisonPolicy, ExpectedResult, MutantDetail, MutationResult
from .oracle_registry import get_oracle


class MutationContext:
    """Inputs for one mutation campaign."""

    __slots__ = ("backend", "candidate_sql", "expected", "policy", "tables", "task")

    def __init__(
        self,
        task: TaskInstance,
        candidate_sql: str,
        tables: dict[str, list[dict[str, Any]]],
        expected: ExpectedResult,
        backend: ExecutionBackend,
        policy: ComparisonPolicy,
    ) -> None:
        self.task = task
        self.candidate_sql = candidate_sql
        self.tables = tables
        self.expected = expected
        self.backend = backend
        self.policy = policy


class MutationOperator:
    """One family-aware incorrect-variant transform."""

    __slots__ = ("mutate", "name")

    def __init__(self, name: str, mutate: Callable[[TaskInstance, str], str | None]) -> None:
        self.name = name
        self.mutate = mutate

    def apply(self, task: TaskInstance, sql: str) -> str | None:
        """Return mutated SQL, or None when not applicable."""
        return self.mutate(task, sql)


def _replace_first(pattern: str, replacement: str, sql: str) -> str | None:
    mutated, count = re.subn(pattern, replacement, sql, count=1, flags=re.IGNORECASE)
    return mutated if count else None


def _op_sum_to_avg(task: TaskInstance, sql: str) -> str | None:
    return _replace_first(r"\bSUM\s*\(", "AVG(", sql)


def _op_count_star_to_distinct_one(task: TaskInstance, sql: str) -> str | None:
    return _replace_first(r"\bCOUNT\s*\(\s*\*\s*\)", "COUNT(DISTINCT 1)", sql)


def _op_flip_first_direction(task: TaskInstance, sql: str) -> str | None:
    if re.search(r"\bDESC\b", sql, re.IGNORECASE):
        return _replace_first(r"\bDESC\b", "ASC", sql)
    if re.search(r"\bASC\b", sql, re.IGNORECASE):
        return _replace_first(r"\bASC\b", "DESC", sql)
    return None


def _op_inner_to_cross(task: TaskInstance, sql: str) -> str | None:
    """Drop the join condition (INNER JOIN -> CROSS JOIN without ON).

    NOTE: inner-to-LEFT is deliberately NOT an operator: with a WHERE
    predicate on right-side columns (the norm in our tasks), LEFT JOIN is
    semantically equivalent to INNER JOIN — an equivalent mutant no suite
    could kill. A missing join condition always changes results instead.
    """
    match = re.search(r"\bINNER\s+JOIN\b", sql, re.IGNORECASE)
    if not match:
        bare = re.search(r"(?<![A-Z_])(JOIN)\b", sql)
        if bare and not re.search(r"\b(LEFT|RIGHT|FULL|CROSS)\s+JOIN\b", sql, re.IGNORECASE):
            start, keyword = bare.start(1), "JOIN"
        else:
            return None
    else:
        start, keyword = match.start(), match.group(0)
    crossed = sql[:start] + "CROSS JOIN" + sql[start + len(keyword) :]
    on_clause = re.search(
        r"\sON\s+[\s\S]*?(?=\sWHERE\b|\sGROUP\s+BY\b|\sORDER\s+BY\b|\sLIMIT\b|\s(?:INNER|LEFT|RIGHT|FULL|CROSS|JOIN)\b|;?\s*$)",
        crossed,
        re.IGNORECASE,
    )
    if not on_clause:
        return None
    return (crossed[: on_clause.start()] + " " + crossed[on_clause.end() :]).strip()


def _op_threshold_to_zero(task: TaskInstance, sql: str) -> str | None:
    return _replace_first(r">\s*\d+(\.\d+)?", "> 0", sql)


def _op_window_widen(task: TaskInstance, sql: str) -> str | None:
    return _replace_first(r"\b30\s*(DAY|day|days|DAYS)\b", r"300 \1", sql)


def _op_drop_where(task: TaskInstance, sql: str) -> str | None:
    match = re.search(
        r"\sWHERE\s+([\s\S]*?)(?=\sGROUP\s+BY|\sORDER\s+BY|\sLIMIT\b|;?\s*$)",
        sql,
        re.IGNORECASE,
    )
    if not match or not match.group(1).strip():
        return None
    return (sql[: match.start()] + " " + sql[match.end() :]).strip()


def _op_partition_swap(task: TaskInstance, sql: str) -> str | None:
    match = re.search(r"PARTITION\s+BY\s+([A-Za-z_][\w.]*)", sql, re.IGNORECASE)
    if not match:
        return None
    current = match.group(1)
    alternatives = [
        c.name
        for t in task.schema_
        for c in t.columns
        if c.name.lower() != current.split(".")[-1].lower()
        and not c.name.lower().endswith("_id")
        and c.name.lower() != "id"
    ]
    if not alternatives:
        return None
    # Prefer a non-unique column that is actually available in the candidate's
    # FROM scope. A previous implementation selected ``name`` from the schema
    # even when the candidate did not join the customers table, producing an
    # invalid mutant rather than a semantic counterexample.
    qualifier = current.split(".", 1)[0] if "." in current else None
    if qualifier:
        # A qualified table alias exposes every column in that table even when
        # the original query does not select/reference the replacement column.
        # Restrict candidates to columns actually present on the aliased table
        # so the mutant remains executable and semantically discriminating.
        alias_match = re.search(
            rf"\b(?:FROM|JOIN)\s+([A-Za-z_]\w*)\s+(?:AS\s+)?{re.escape(qualifier)}\b",
            sql,
            re.IGNORECASE,
        )
        alias_table = alias_match.group(1).lower() if alias_match else None
        table_columns = {
            table.name.lower(): {column.name.lower() for column in table.columns}
            for table in task.schema_
        }
        available = [
            col
            for col in alternatives
            if alias_table in table_columns and col.lower() in table_columns[alias_table]
        ]
    else:
        available = [
            col for col in alternatives if re.search(rf"\b{col}\b", sql, re.IGNORECASE)
        ]
    preferred = [col for col in ("country", "amount") if col in available]
    replacement = (preferred[0] if preferred else (available[0] if available else alternatives[0]))
    if "." in current:
        replacement = f"{current.split('.', 1)[0]}.{replacement}"
    return sql[: match.start(1)] + replacement + sql[match.end(1) :]


def _partition_mutation_tables(
    task: TaskInstance, tables: dict[str, list[dict[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    """Create a minimal discriminating fixture for partition-column mutation.

    The production fixtures may have unique customer countries, making a
    partition-by-country mutant observationally equivalent to partitioning by
    customer. This mutation-only fixture keeps the task/spec unchanged while
    forcing two qualifying customers into one country partition.
    """
    derived = deepcopy(tables)
    customers = derived.get("customers", [])
    orders = derived.get("orders", [])
    if len(customers) < 2 or len(orders) < 2:
        return derived
    customer_ids = [customers[0]["customer_id"], customers[1]["customer_id"]]
    shared_country = customers[0].get("country") or "ZZ"
    customers[0]["country"] = shared_country
    customers[1]["country"] = shared_country
    year = str(task.requirements.get("year", "2025"))
    qualifying = [
        row
        for row in orders
        if str(row.get("order_date", "")).startswith(year)
    ]
    if len(qualifying) < 2:
        qualifying = orders[:2]
    # Ensure the two shared-country partitions both have a qualifying order.
    qualifying[0]["customer_id"] = customer_ids[0]
    qualifying[0]["status"] = str(task.requirements.get("status_filter", "completed"))
    qualifying[1]["customer_id"] = customer_ids[1]
    qualifying[1]["status"] = str(task.requirements.get("status_filter", "completed"))
    qualifying[0]["amount"] = 10.0
    qualifying[1]["amount"] = 900.0
    return derived


def _cte_where_mutation_tables(
    task: TaskInstance, tables: dict[str, list[dict[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    """Make dropping the CTE year filter observably wrong without changing the task."""
    derived = deepcopy(tables)
    orders = derived.get("orders", [])
    if not orders:
        return derived
    row = orders[0]
    row["order_date"] = "2024-12-31"
    row["status"] = str(task.requirements.get("status_filter", "completed"))
    row["amount"] = 999999.0
    return derived


def _cte_aggregate_mutation_tables(
    task: TaskInstance, tables: dict[str, list[dict[str, Any]]]
) -> dict[str, list[dict[str, Any]]]:
    """Ensure SUM and AVG differ inside one qualifying customer-month."""
    derived = deepcopy(tables)
    orders = derived.get("orders", [])
    if len(orders) < 2:
        return derived
    year = str(task.requirements.get("year", "2025"))
    orders[0].update({"customer_id": 1, "order_date": f"{year}-02-01", "status": "completed", "amount": 10.0})
    orders[1].update({"customer_id": 1, "order_date": f"{year}-02-02", "status": "completed", "amount": 999999.0})
    return derived


OPERATORS: dict[str, MutationOperator] = {
    "agg-sum-to-avg": MutationOperator("agg-sum-to-avg", _op_sum_to_avg),
    "agg-count-distinct-one": MutationOperator(
        "agg-count-distinct-one", _op_count_star_to_distinct_one
    ),
    "order-flip": MutationOperator("order-flip", _op_flip_first_direction),
    "join-inner-to-cross": MutationOperator("join-inner-to-cross", _op_inner_to_cross),
    "threshold-to-zero": MutationOperator("threshold-to-zero", _op_threshold_to_zero),
    "window-widen-30-to-300": MutationOperator("window-widen-30-to-300", _op_window_widen),
    "partition-column-swap": MutationOperator("partition-column-swap", _op_partition_swap),
    "where-clause-drop": MutationOperator("where-clause-drop", _op_drop_where),
}

OPERATORS_BY_FAMILY: dict[str, list[str]] = {
    "simple_joins": ["agg-sum-to-avg", "order-flip", "join-inner-to-cross", "where-clause-drop"],
    "multi_joins": ["agg-sum-to-avg", "order-flip", "join-inner-to-cross", "where-clause-drop"],
    "aggregation": ["agg-sum-to-avg", "agg-count-distinct-one", "order-flip"],
    # NOTE: where-clause-drop is excluded for aggregation: the template's
    # WHERE holds only the year filter and every generated fixture date lies
    # in that year, so the mutant is equivalent on all possible fixtures.
    "cte": ["agg-sum-to-avg", "order-flip", "where-clause-drop"],
    "subqueries": ["threshold-to-zero", "join-inner-to-cross", "where-clause-drop"],
    "window_functions": [
        "partition-column-swap",
        "order-flip",
        "agg-sum-to-avg",
        "where-clause-drop",
    ],
    "temporal": ["order-flip", "threshold-to-zero", "where-clause-drop"],
    "deduplication": ["order-flip", "threshold-to-zero", "where-clause-drop"],
    "retention": ["window-widen-30-to-300", "order-flip", "where-clause-drop"],
    "funnel": ["order-flip", "threshold-to-zero", "where-clause-drop"],
}


def applicable_operators(
    task: TaskInstance, sql: str, max_mutations: int
) -> list[MutationOperator]:
    """Operators whose transform applies, capped for cost control."""
    chosen: list[MutationOperator] = []
    for name in OPERATORS_BY_FAMILY.get(task.family, []):
        mutated = OPERATORS[name].apply(task, sql)
        if mutated is not None and mutated != sql:
            chosen.append(OPERATORS[name])
        if len(chosen) >= max_mutations:
            break
    return chosen


def run_mutation_checks(
    ctx: MutationContext, max_mutations: int, min_score: float
) -> MutationResult:
    """Execute each applicable mutant; killed = suite rejects it."""
    operators = applicable_operators(ctx.task, ctx.candidate_sql, max_mutations)
    details: list[MutantDetail] = []
    caught = survived = invalid = inconclusive = 0
    for operator in operators:
        mutated = operator.apply(ctx.task, ctx.candidate_sql)
        assert mutated is not None
        mutation_tables = ctx.tables
        mutation_expected = ctx.expected
        if operator.name == "partition-column-swap":
            mutation_tables = _partition_mutation_tables(ctx.task, ctx.tables)
            # The fixture is intentionally changed only for this mutation
            # campaign. Recompute expected rows with the independent oracle;
            # never compare the mutant against stale original-fixture rows.
            oracle = get_oracle(ctx.task.template_id, ctx.task.template_version)
            mutation_expected = oracle.fn(dict(ctx.task.requirements), mutation_tables)
        elif operator.name == "where-clause-drop" and ctx.task.family == "cte":
            mutation_tables = _cte_where_mutation_tables(ctx.task, ctx.tables)
            oracle = get_oracle(ctx.task.template_id, ctx.task.template_version)
            mutation_expected = oracle.fn(dict(ctx.task.requirements), mutation_tables)
        elif operator.name == "agg-sum-to-avg" and ctx.task.family == "cte":
            mutation_tables = _cte_aggregate_mutation_tables(ctx.task, ctx.tables)
            oracle = get_oracle(ctx.task.template_id, ctx.task.template_version)
            mutation_expected = oracle.fn(dict(ctx.task.requirements), mutation_tables)
        mutant_candidate = CandidateSolution(
            candidate_id=f"mutant-{operator.name}",
            task_id=ctx.task.task_id,
            model="mutation-harness",
            model_revision="n/a",
            prompt_version="n/a",
            generation_schema_version="n/a",
            provider="mutation-harness",
            endpoint_id="mutation-harness",
            candidate_index=0,
            raw_response=mutated,
            candidate_sql=mutated,
            generation_config={"temperature": 0.0, "top_p": 1.0, "max_tokens": 1},
            generation_timestamp="1970-01-01T00:00:00+00:00",
            generation_duration_ms=0,
        )
        try:
            execution = ctx.backend.run(
                ctx.task, mutant_candidate, mutation_tables, f"mutation:{operator.name}"
            )
        except Exception:  # noqa: BLE001 — backend faults exclude the mutant
            inconclusive += 1
            details.append(
                MutantDetail(
                    operator=operator.name,
                    caught=False,
                    classification="INFRA_INCONCLUSIVE",
                    reason="backend-inconclusive",
                )
            )
            continue
        if execution.status in ("SANDBOX_ERROR",):
            inconclusive += 1
            details.append(
                MutantDetail(
                    operator=operator.name,
                    caught=False,
                    classification="INFRA_INCONCLUSIVE",
                    reason=f"infra-{execution.status}",
                )
            )
            continue
        if execution.status != "SUCCEEDED" or execution.result_data is None:
            # Invalid SQL is evidence about the mutation operator, not evidence
            # that the verification suite can distinguish wrong semantics.
            invalid += 1
            details.append(
                MutantDetail(
                    operator=operator.name,
                    caught=False,
                    classification="INVALID_MUTANT",
                    reason=f"execution-{execution.status}",
                )
            )
            continue
        comparison = compare_mod.compare(
            mutation_expected,
            [c.name for c in execution.result_data.columns],
            execution.result_data.rows,
            ctx.policy,
        )
        if comparison.match:
            survived += 1
            details.append(
                MutantDetail(
                    operator=operator.name,
                    caught=False,
                    classification="SURVIVED",
                    reason="mutant-passed",
                )
            )
        else:
            caught += 1
            details.append(
                MutantDetail(
                    operator=operator.name,
                    caught=True,
                    classification="SEMANTIC_KILL",
                    reason="result-mismatch",
                )
            )
    decided = caught + survived
    score = (caught / decided) if decided else None
    return MutationResult(
        applicable=len(operators),
        run=len(operators),
        caught=caught,
        semantic_kills=caught,
        survived=survived,
        invalid=invalid,
        inconclusive=inconclusive,
        mutation_score=score,
        min_score=min_score,
        details=details,
    )
