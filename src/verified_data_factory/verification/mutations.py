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

import hashlib
import re
import time
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.task_engine.models import TaskInstance

from . import comparator as compare_mod
from .backend import ExecutionBackend
from .behavior_authority import public_behavior_map
from .models import ComparisonPolicy, ExpectedResult, MutantDetail, MutationResult
from .oracle_registry import get_oracle
from .public_rule_proofs import public_proofs


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


def _op_count_distinct_to_count(task: TaskInstance, sql: str) -> str | None:
    return _replace_first(r"\bCOUNT\s*\(\s*DISTINCT\s+[^)]+\)", "COUNT(*)", sql)


def _op_flip_first_direction(task: TaskInstance, sql: str) -> str | None:
    if re.search(r"\bDESC\b", sql, re.IGNORECASE):
        return _replace_first(r"\bDESC\b", "ASC", sql)
    if re.search(r"\bASC\b", sql, re.IGNORECASE):
        return _replace_first(r"\bASC\b", "DESC", sql)
    return None


def _op_grade_valid_filter_drop(task: TaskInstance, sql: str) -> str | None:
    return _replace_first(r"\bWHERE\s+revision_status\s*=\s*'valid'\s*", "", sql)


def _op_grade_time_flip(task: TaskInstance, sql: str) -> str | None:
    return _replace_first(r"\brecorded_at\s+DESC\b", "recorded_at ASC", sql)


def _op_grade_tie_flip(task: TaskInstance, sql: str) -> str | None:
    return _replace_first(r"\brevision_id\s+DESC\b", "revision_id ASC", sql)


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


_WHERE_TERMINATORS = (
    "GROUP BY",
    "ORDER BY",
    "LIMIT",
    "QUALIFY",
    "HAVING",
    "UNION",
    "EXCEPT",
    "INTERSECT",
    "WINDOW",
)


def _paren_depth(text: str, offset: int) -> int:
    return text[:offset].count("(") - text[:offset].count(")")


def _op_union_to_union_all(task: TaskInstance, sql: str) -> str | None:
    """Replace a deduplicating UNION with UNION ALL (keeps duplicate identities)."""
    return _replace_first(r"\bUNION\b(?!\s+ALL)", "UNION ALL", sql)


def _op_captured_to_failed(task: TaskInstance, sql: str) -> str | None:
    return _replace_first(r"'captured'", "'failed'", sql)


def _op_approval_to_rejected(task: TaskInstance, sql: str) -> str | None:
    return _replace_first(r"'approved'", "'rejected'", sql)


def _op_sla_boundary_exclusive(task: TaskInstance, sql: str) -> str | None:
    return _replace_first(r"\b72\s+HOUR\b", "71 HOUR", sql)


def _op_passed_to_failed(task: TaskInstance, sql: str) -> str | None:
    return _replace_first(r"'passed'", "'failed'", sql)


def _op_stage_order_reverse(task: TaskInstance, sql: str) -> str | None:
    return _replace_first(r"earlier\.stage_number\s*<\s*later\.stage_number", "earlier.stage_number > later.stage_number", sql)


def _op_drop_where(task: TaskInstance, sql: str) -> str | None:
    """Remove one WHERE clause, respecting its parenthesis scope.

    A naive regex terminates at ``GROUP BY``/``ORDER BY``/end and therefore
    deletes across a closing parenthesis in CTE and subquery candidates,
    producing invalid SQL rather than a semantic counterexample. This
    scanner stops at the ``)`` that closes the WHERE's own scope (or at a
    sibling clause at the same depth), so the mutant stays executable.
    """
    match = re.search(r"\bWHERE\b", sql, re.IGNORECASE)
    if not match:
        return None
    base_depth = _paren_depth(sql, match.start())
    depth = base_depth
    index = match.end()
    end = len(sql)
    while index < len(sql):
        char = sql[index]
        if char in {"'", '"'}:
            quote = char
            index += 1
            while index < len(sql):
                if sql[index] == quote:
                    if index + 1 < len(sql) and sql[index + 1] == quote:
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == base_depth:
                end = index
                break
            depth -= 1
        elif depth == base_depth:
            tail = sql[index:].upper()
            if any(re.match(re.escape(token) + r"\b", tail) for token in _WHERE_TERMINATORS):
                end = index
                break
        index += 1
    condition = sql[match.end() : end].strip()
    if not condition:
        return None
    return (sql[: match.start()] + " " + sql[end:]).strip()


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
    "output-row-drop": MutationOperator("output-row-drop", lambda task, sql: f"SELECT * FROM ({sql.strip().rstrip(';')}) AS mutation_output WHERE FALSE"),
    "output-row-duplicate": MutationOperator("output-row-duplicate", lambda task, sql: f"WITH mutation_output AS ({sql.strip().rstrip(';')}) SELECT * FROM mutation_output UNION ALL SELECT * FROM mutation_output"),
    "year-to-prior-year": MutationOperator("year-to-prior-year", lambda task, sql: _replace_first(r"\b2025\b", "2024", sql)),
    "passing-score-to-zero": MutationOperator("passing-score-to-zero", lambda task, sql: _replace_first(r">=\s*50\b", ">= 0", sql)),
    "passing-boundary-exclusive": MutationOperator("passing-boundary-exclusive", lambda task, sql: _replace_first(r">=\s*50\b", "> 50", sql)),
    "lag-to-lead": MutationOperator("lag-to-lead", lambda task, sql: _replace_first(r"\bLAG\s*\(", "LEAD(", sql)),
    "assignment-to-opened": MutationOperator("assignment-to-opened", lambda task, sql: _replace_first(r"'assigned'", "'opened'", sql)),
    "agg-sum-to-avg": MutationOperator("agg-sum-to-avg", _op_sum_to_avg),
    "agg-count-distinct-one": MutationOperator(
        "agg-count-distinct-one", _op_count_star_to_distinct_one
    ),
    "count-distinct-to-count": MutationOperator("count-distinct-to-count", _op_count_distinct_to_count),
    "order-flip": MutationOperator("order-flip", _op_flip_first_direction),
    "join-inner-to-cross": MutationOperator("join-inner-to-cross", _op_inner_to_cross),
    "threshold-to-zero": MutationOperator("threshold-to-zero", _op_threshold_to_zero),
    "window-widen-30-to-300": MutationOperator("window-widen-30-to-300", _op_window_widen),
    "partition-column-swap": MutationOperator("partition-column-swap", _op_partition_swap),
    "where-clause-drop": MutationOperator("where-clause-drop", _op_drop_where),
    "grade-valid-filter-drop": MutationOperator(
        "grade-valid-filter-drop", _op_grade_valid_filter_drop
    ),
    "grade-time-flip": MutationOperator("grade-time-flip", _op_grade_time_flip),
    "grade-tie-flip": MutationOperator("grade-tie-flip", _op_grade_tie_flip),
    "union-to-union-all": MutationOperator("union-to-union-all", _op_union_to_union_all),
    "captured-to-failed": MutationOperator("captured-to-failed", _op_captured_to_failed),
    "approval-to-rejected": MutationOperator("approval-to-rejected", _op_approval_to_rejected),
    "sla-boundary-exclusive": MutationOperator("sla-boundary-exclusive", _op_sla_boundary_exclusive),
    "passed-to-failed": MutationOperator("passed-to-failed", _op_passed_to_failed),
    "stage-order-reverse": MutationOperator("stage-order-reverse", _op_stage_order_reverse),
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

# The payments task includes explicit cross-year ledger rows, unlike the
# original aggregation task. Dropping its WHERE clause is meaningful there.
OPERATORS_BY_TEMPLATE: dict[str, list[str]] = {
    **{
        template_id: ["agg-sum-to-avg", "order-flip", "where-clause-drop"]
        for template_id in (
            "sql.joins.payments_country_transfer", "sql.joins.clinic_scheduled_clinician", "sql.joins.manufacturing_approved_supplier", "sql.joins.education_completed_enrollment", "sql.aggregation.manufacturing_line_scrap", "sql.cte.saas_mrr_changes", "sql.cte.logistics_depot_delay", "sql.subqueries.payments_no_settlement", "sql.subqueries.support_unresolved_reopen", "sql.windows.payments_risk_rank", "sql.windows.logistics_previous_stop", "sql.temporal.saas_trial_activation", "sql.temporal.inventory_daily_stock", "sql.dedup.refund_prefer_approved", "sql.dedup.payments_latest_profile", "sql.retention.media_week_two_return", "sql.retention.clinic_followup_window", "sql.funnel.saas_activation_payment", "sql.funnel.logistics_parcel_delivery",
        )
    },
    "sql.joins.logistics_final_leg": ["join-inner-to-cross", "year-to-prior-year", "where-clause-drop"],
    "sql.cte.inventory_net_flow": ["agg-sum-to-avg", "year-to-prior-year", "order-flip"],
    "sql.subqueries.education_all_required": ["passing-score-to-zero", "passing-boundary-exclusive", "where-clause-drop"],
    "sql.windows.media_previous_play": ["lag-to-lead", "year-to-prior-year", "where-clause-drop"],
    "sql.temporal.clinic_weekly_visits": ["agg-count-distinct-one", "year-to-prior-year", "where-clause-drop"],
    "sql.temporal.media_first_full_week_viewers": ["count-distinct-to-count", "year-to-prior-year"],
    "sql.temporal.manufacturing_shift_downtime": ["agg-sum-to-avg", "year-to-prior-year", "order-flip"],
    "sql.temporal.logistics_service_level_as_of": ["year-to-prior-year", "order-flip", "where-clause-drop"],
    "sql.temporal.saas_account_snapshot": ["agg-sum-to-avg", "order-flip", "where-clause-drop"],
    "sql.retention.saas_repeat_payment": ["window-widen-30-to-300", "year-to-prior-year", "order-flip"],
    "sql.funnel.support_resolution_chain": ["assignment-to-opened", "year-to-prior-year", "order-flip"],
    "sql.aggregation.warehouse_throughput": ["agg-sum-to-avg", "where-clause-drop", "order-flip"],
    "sql.aggregation.top_category_sales": ["agg-sum-to-avg", "where-clause-drop", "order-flip"],
    "sql.aggregation.fulfillment_sla_dashboard": ["agg-count-distinct-one", "where-clause-drop", "order-flip"],
    "sql.aggregation.product_unique_conversion": ["count-distinct-to-count", "where-clause-drop", "order-flip"],
    "sql.cte.order_line_reconciliation": ["agg-sum-to-avg", "where-clause-drop", "order-flip"],
    "sql.cte.category_descendant_sales": ["where-clause-drop", "order-flip"],
    "sql.cte.session_funnel_completion": ["agg-count-distinct-one", "order-flip"],
    "sql.cte.customer_first_month_repeat": ["order-flip", "where-clause-drop"],
    "sql.subqueries.customer_outreach": ["union-to-union-all", "where-clause-drop", "order-flip"],
    "sql.funnel.checkout_paid_session": ["captured-to-failed", "order-flip"],
    "sql.funnel.kyc_document_approval": ["approval-to-rejected", "order-flip"],
    "sql.funnel.parcel_exception_recovery": ["sla-boundary-exclusive", "order-flip", "where-clause-drop"],
    "sql.funnel.curriculum_gate_completion": ["passed-to-failed", "stage-order-reverse"],
    "sql.aggregation.payment_net_settled": [
        "agg-sum-to-avg", "order-flip", "where-clause-drop"
    ],
    "sql.aggregation.support_sla_breaches": [
        "agg-count-distinct-one", "order-flip", "where-clause-drop"
    ],
    "sql.dedup.education_grade_revisions": [
        "grade-valid-filter-drop", "grade-time-flip", "grade-tie-flip"
    ],
}


def applicable_operators(
    task: TaskInstance, sql: str, max_mutations: int
) -> list[MutationOperator]:
    """Operators whose transform applies, capped for cost control."""
    chosen: list[MutationOperator] = []
    if max_mutations <= 0:
        return chosen
    names = OPERATORS_BY_TEMPLATE.get(task.template_id, OPERATORS_BY_FAMILY.get(task.family, []))
    for name in names:
        mutated = OPERATORS[name].apply(task, sql)
        if mutated is not None and mutated != sql:
            chosen.append(OPERATORS[name])
        if len(chosen) >= max_mutations:
            break
    # A small template-specific list does not establish minimum discrimination.
    # These distinct valid output-neighbor queries test omission/multiplicity.
    for name in ("output-row-drop", "output-row-duplicate"):
        if not chosen or len(chosen) >= min(3, max_mutations):
            break
        chosen.append(OPERATORS[name])
    return chosen


def run_mutation_checks(
    ctx: MutationContext, max_mutations: int, min_score: float
) -> MutationResult:
    """Execute each applicable mutant; killed = suite rejects it."""
    authority = public_behavior_map(ctx.task)
    if authority.granular and authority.task_matches_public_contract:
        reference, proofs = public_proofs(ctx.task)
        if ctx.candidate_sql == reference:
            return _public_candidate_mutations(ctx, proofs, max_mutations, min_score)
        from .qualification.delivery_profiles import candidate_specs, get_profile

        followup = get_profile(ctx.task.template_id, ctx.task.template_version)
        if followup is not None:
            derived = candidate_specs(followup, ctx.candidate_sql, reference, proofs)
            if derived is not None:
                return _public_candidate_mutations(ctx, derived, max_mutations, min_score)
        if (ctx.task.template_id, ctx.task.template_version) == ("sql.dedup.lowest_quote", 1):
            from .qualification.lowest_quote_candidate_transforms import (
                candidate_proofs as quote_proofs,
            )

            derived = quote_proofs(ctx.candidate_sql, reference, proofs)
            if derived is not None:
                return _public_candidate_mutations(ctx, derived, max_mutations, min_score)
        if (ctx.task.template_id, ctx.task.template_version) == ("sql.dedup.education_grade_revisions", 2):
            from .qualification.grade_candidate_transforms import candidate_proofs as grade_proofs

            derived = grade_proofs(ctx.candidate_sql, reference, proofs)
            if derived is not None:
                return _public_candidate_mutations(ctx, derived, max_mutations, min_score)
        if (ctx.task.template_id, ctx.task.template_version) == ("sql.windows.media_previous_play", 1):
            from .qualification.playback_candidate_transforms import (
                candidate_proofs as playback_proofs,
            )

            derived = playback_proofs(ctx.candidate_sql, reference, proofs)
            if derived is not None:
                return _public_candidate_mutations(ctx, derived, max_mutations, min_score)
        if (ctx.task.template_id, ctx.task.template_version) == ("sql.aggregation.fulfillment_sla_dashboard", 1):
            from .qualification.sla_candidate_transforms import candidate_proofs

            derived = candidate_proofs(ctx.candidate_sql, proofs)
            if derived is not None:
                return _public_candidate_mutations(ctx, derived, max_mutations, min_score)
        else:
            from .qualification.alternative_candidate_transforms import (
                candidate_proofs as alternative_proofs,
            )

            derived = alternative_proofs(ctx.task.template_id, ctx.task.template_version, ctx.candidate_sql, reference, proofs)
            if derived is not None:
                return _public_candidate_mutations(ctx, derived, max_mutations, min_score)
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
        began = time.monotonic()
        sql_hash = hashlib.sha256(mutated.encode()).hexdigest()
        try:
            execution = ctx.backend.run(
                ctx.task, mutant_candidate, mutation_tables, f"mutation:{operator.name}"
            )
        except Exception as exc:  # noqa: BLE001 — backend faults exclude the mutant
            inconclusive += 1
            details.append(
                MutantDetail(
                    operator=operator.name,
                    caught=False,
                    classification="INFRA_INCONCLUSIVE",
                    reason=re.sub(r"(?i)(bearer\s+|(?:token|password|api_key)\s*[=:]\s*)\S+", r"\1[REDACTED]", f"{type(exc).__name__}: {exc}")[:500],
                    sql_sha256=sql_hash, duration_ms=int((time.monotonic() - began) * 1000),
                    failure_code="BACKEND_EXCEPTION",
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
                    sql_sha256=sql_hash, execution_id=execution.execution_id,
                    duration_ms=execution.duration_ms,
                    failure_code=execution.failure.code if execution.failure else execution.status,
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
                    sql_sha256=sql_hash, execution_id=execution.execution_id,
                    duration_ms=execution.duration_ms,
                    failure_code=execution.failure.code if execution.failure else execution.status,
                )
            )
            continue
        comparison = compare_mod.compare(
            mutation_expected,
            [c.name for c in execution.result_data.columns],
            execution.result_data.rows,
            ctx.policy,
            column_types=[c.type for c in execution.result_data.columns],
        )
        if comparison.match:
            survived += 1
            details.append(
                MutantDetail(
                    operator=operator.name,
                    caught=False,
                    classification="SURVIVED",
                    reason="mutant-passed",
                    sql_sha256=sql_hash, execution_id=execution.execution_id, duration_ms=execution.duration_ms,
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
                    sql_sha256=sql_hash, execution_id=execution.execution_id, duration_ms=execution.duration_ms,
                )
            )
    authority = public_behavior_map(ctx.task)
    # Generic operator names are not requirement-specific discriminator proofs.
    # Retain kills/score, but leave rule attribution unproven rather than invent it.
    required_rules = sorted(authority.semantic_rule_ids)
    covered_rules = sorted({rule for d in details if d.classification == "SEMANTIC_KILL" for rule in d.rule_ids})
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
        covered_rules=covered_rules,
        required_rules=required_rules,
        coverage_complete=(
            authority.task_matches_public_contract
            and caught >= 3
            and len({d.sql_sha256 for d in details if d.classification == "SEMANTIC_KILL"}) >= 3
            and bool(required_rules)
            and set(required_rules) <= set(covered_rules)
        ),
    )


def _public_candidate_mutations(
    ctx: MutationContext, proofs: dict[str, Any], maximum: int, minimum: float,
) -> MutationResult:
    """Execute candidate-derived canonical transforms on their attributed fixtures.

    Canonical SQL and explicitly supported candidate-derived SLA AST transforms
    use this path. Other formulations retain generic UNKNOWN coverage.
    """
    from verified_data_factory.task_engine.hidden_fixtures import fixture_fingerprint

    authority = public_behavior_map(ctx.task)
    groups: dict[tuple[str, str], tuple[dict[str, Any], list[str]]] = {}
    for rule in authority.rules:
        if rule.kind != "semantic":
            continue
        proof = proofs[rule.proof_key]
        key = (proof["wrong_sql"], fixture_fingerprint(ctx.task, proof["witness"]))
        if key not in groups:
            groups[key] = (proof, [])
        groups[key][1].append(rule.rule_id)
    details = []
    candidate_hash = hashlib.sha256(ctx.candidate_sql.encode()).hexdigest()
    for index, ((sql, fingerprint), (proof, rule_ids)) in enumerate(list(groups.items())[:maximum]):
        def solution(text: str, label: str, slot: int = index) -> CandidateSolution:
            return CandidateSolution(
                candidate_id=f"{ctx.task.task_id}.public-{slot}-{label}", task_id=ctx.task.task_id,
                model="candidate-public-rule-replay", model_revision="1", prompt_version="none",
                generation_schema_version="1.0", provider="local-reference-transform",
                endpoint_id="none", candidate_index=0, raw_response=text, candidate_sql=text,
                generation_config={"temperature": 0.0, "top_p": 1.0, "max_tokens": 1},
                generation_timestamp="1970-01-01T00:00:00+00:00", generation_duration_ms=0,
            )
        expected = get_oracle(ctx.task.template_id, ctx.task.template_version).fn(
            ctx.task.requirements, proof["witness"],
        )
        try:
            correct = ctx.backend.run(ctx.task, solution(ctx.candidate_sql, "candidate"),
                                      proof["witness"], f"public:{index}:candidate")
            wrong = ctx.backend.run(ctx.task, solution(sql, "mutant"),
                                    proof["witness"], f"public:{index}:mutant")
        except Exception as exc:  # noqa: BLE001 — execution failure cannot establish coverage
            details.append(MutantDetail(operator=f"public:{index}", caught=False,
                           classification="INFRA_INCONCLUSIVE", reason=type(exc).__name__,
                           candidate_sql_sha256=candidate_hash, fixture_sha256=fingerprint))
            continue
        classification: Any = "INFRA_INCONCLUSIVE"
        caught = False
        if correct.status == "SUCCEEDED" and correct.result_data is not None:
            data = correct.result_data
            agrees = compare_mod.compare(expected, [c.name for c in data.columns], data.rows,
                                         ctx.policy, column_types=[c.type for c in data.columns]).match
            if agrees and wrong.status == "SUCCEEDED" and wrong.result_data is not None:
                data = wrong.result_data
                caught = not compare_mod.compare(expected, [c.name for c in data.columns], data.rows,
                                                  ctx.policy, column_types=[c.type for c in data.columns]).match
                classification = "SEMANTIC_KILL" if caught else "SURVIVED"
            elif agrees and wrong.status not in {"SANDBOX_ERROR", "TIMEOUT"}:
                classification = "INVALID_MUTANT"
        details.append(MutantDetail(
            operator=f"public:{index}", caught=caught, classification=classification,
            reason="executed clause-specific candidate and mutant", sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
            execution_id=wrong.execution_id, candidate_execution_id=correct.execution_id,
            candidate_sql_sha256=candidate_hash, fixture_sha256=fingerprint,
            rule_ids=rule_ids if caught else [],
            retained_executions={"candidate": correct.model_dump(mode="json"),
                                 "mutant": wrong.model_dump(mode="json"),
                                 "expected": expected.model_dump(mode="json"), "tables": proof["witness"],
                                 "candidate_sql": ctx.candidate_sql, "mutant_sql": sql},
        ))
    counts = {name: sum(d.classification == name for d in details) for name in
              ("SEMANTIC_KILL", "SURVIVED", "INVALID_MUTANT", "INFRA_INCONCLUSIVE")}
    covered = sorted({r for d in details for r in d.rule_ids})
    kills, survived = counts["SEMANTIC_KILL"], counts["SURVIVED"]
    distinct = {d.sql_sha256 for d in details if d.caught}
    return MutationResult(
        applicable=len(groups), run=len(details), caught=kills, semantic_kills=kills,
        survived=survived, invalid=counts["INVALID_MUTANT"], inconclusive=counts["INFRA_INCONCLUSIVE"],
        mutation_score=kills / (kills + survived) if kills + survived else None,
        min_score=minimum, details=details, covered_rules=covered,
        required_rules=sorted(authority.semantic_rule_ids),
        coverage_complete=len(distinct) >= 3 and set(covered) == set(authority.semantic_rule_ids),
    )
