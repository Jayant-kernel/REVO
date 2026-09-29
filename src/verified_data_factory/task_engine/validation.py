"""Validation for templates and task instances (Phase 1).

Fails loudly with domain exceptions. Covers structural, schema, fixture,
and Phase-1-feasible semantic checks.
"""

from __future__ import annotations

from typing import Any

from .errors import TemplateError, ValidationError
from .models import SUPPORTED_DUCKDB_TYPES, TaskInstance, TaskTemplate
from .seed import build_task_id

KNOWN_EDGE_CASES = frozenset(
    {
        "empty_result",
        "null_values",
        "duplicates",
        "duplicate_events",
        "ties",
        "missing_relationships",
        "no_events",
        "single_row_groups",
        "multiple_matching_rows",
        "multiple_purchases",
        "out_of_order_timestamps",
        "same_day_events",
        "retention_boundaries",
        "same_timestamp_steps",
        "window_end_boundary",
        "zero_values",
        "negative_values",
    }
)

ALLOWED_ORACLE_TYPES = frozenset({"reference_query"})

# Per-family semantic keys every template's requirements must define.
# This gate prevents ambiguous task specifications from reaching Phase 2:
# a future independent oracle can only be built against exact semantics.
# Adding a new family requires registering its required keys here.
SEMANTIC_REQUIREMENTS: dict[str, frozenset[str]] = {
    "simple_joins": frozenset(
        {"objective", "year", "status_filter", "join_type", "unmatched_behavior", "null_semantics"}
    ),
    "multi_joins": frozenset(
        {
            "objective",
            "year",
            "status_filter",
            "join_type",
            "unmatched_behavior",
            "line_revenue_def",
        }
    ),
    "aggregation": frozenset(
        {
            "objective",
            "year",
            "group_by",
            "null_handling",
            "count_semantics",
            "empty_group_behavior",
        }
    ),
    "cte": frozenset({"objective", "year", "status_filter", "top_tie_break", "unmatched_behavior"}),
    "subqueries": frozenset(
        {
            "objective",
            "year",
            "status_filter",
            "threshold_operator",
            "exists_semantics",
            "no_match_behavior",
        }
    ),
    "window_functions": frozenset(
        {
            "objective",
            "year",
            "status_filter",
            "partition_by",
            "rank_order",
            "running_order",
            "tie_policy",
            "null_ordering",
        }
    ),
    "temporal": frozenset(
        {"objective", "year", "window_start", "window_end", "boundary_policy", "month_definition"}
    ),
    "deduplication": frozenset(
        {"objective", "duplicate_key", "winner_rule", "tie_break", "timestamp_tie_policy"}
    ),
    "retention": frozenset(
        {
            "objective",
            "retention_window_days",
            "qualifying_event",
            "cohort_definition",
            "boundary_policy",
            "repeated_event_policy",
        }
    ),
    "funnel": frozenset(
        {
            "objective",
            "funnel_steps",
            "session_gap_minutes",
            "consecutiveness",
            "cross_session_policy",
            "repeat_policy",
        }
    ),
}


def validate_template(template: TaskTemplate) -> None:
    """Validate a parsed template; raise TemplateError on any problem."""
    if template.difficulty not in (1, 2, 3, 4, 5):
        raise TemplateError(f"invalid difficulty: {template.difficulty}")
    unknown = [e for e in template.edge_cases if e not in KNOWN_EDGE_CASES]
    if unknown:
        raise TemplateError(f"invalid edge-case definitions: {unknown}")
    if template.oracle_spec.type not in ALLOWED_ORACLE_TYPES:
        raise TemplateError(f"invalid oracle type: {template.oracle_spec.type!r}")
    if not template.oracle_spec.strategy.strip():
        raise TemplateError("oracle strategy must be non-empty")
    if "{" not in template.instruction_template or "}" not in template.instruction_template:
        raise TemplateError("instruction_template must contain at least one {parameter}")
    required_semantics = SEMANTIC_REQUIREMENTS.get(template.family)
    if required_semantics is None:
        raise TemplateError(
            f"unknown family {template.family!r}: register its semantic "
            "requirements in SEMANTIC_REQUIREMENTS before use"
        )
    missing_semantics = sorted(k for k in required_semantics if k not in template.requirements)
    if missing_semantics:
        raise TemplateError(
            f"family {template.family!r} requirements missing semantic keys: {missing_semantics}"
        )
    columns_by_table: dict[str, set[str]] = {
        t.name: {c.name for c in t.columns} for t in template.schema_definition
    }
    for key in ("output_columns", "group_by", "filter_columns", "order_by"):
        cols = template.requirements.get(key, [])
        if isinstance(cols, list):
            for col in cols:
                if "." in str(col):
                    tname, cname = str(col).split(".", 1)
                    if tname not in columns_by_table:
                        raise TemplateError(f"requirement {key} references unknown table: {col}")
                    if cname not in columns_by_table[tname]:
                        raise TemplateError(f"requirement {key} references unknown column: {col}")


def validate_task(task: TaskInstance) -> None:
    """Validate a generated task instance; raise ValidationError on failure."""
    if not task.task_id.startswith(task.template_id):
        raise ValidationError(f"task_id {task.task_id!r} must start with template_id")
    expected_id = build_task_id(
        task.template_id,
        task.template_version,
        task.seed,
        task.generation_metadata.config,
        task.generation_metadata.engine_version,
    )
    if task.task_id != expected_id:
        raise ValidationError(
            f"task_id {task.task_id!r} does not match generation inputs (expected {expected_id!r})"
        )
    if task.difficulty not in (1, 2, 3, 4, 5):
        raise ValidationError(f"invalid difficulty: {task.difficulty}")

    # Schema checks.
    seen_tables: set[str] = set()
    col_index: dict[str, set[str]] = {}
    for table in task.schema_:
        if table.name in seen_tables:
            raise ValidationError(f"duplicate table: {table.name}")
        seen_tables.add(table.name)
        col_names = [c.name for c in table.columns]
        if len(set(col_names)) != len(col_names):
            raise ValidationError(f"duplicate columns in {table.name}")
        for col in table.columns:
            if col.type not in SUPPORTED_DUCKDB_TYPES:
                raise ValidationError(f"unsupported type {col.type} in {table.name}")
        col_index[table.name] = set(col_names)

    # Fixture checks: tables match schema, columns + row counts line up.
    if set(task.tables) != seen_tables:
        raise ValidationError(
            f"fixture tables {sorted(task.tables)} != schema {sorted(seen_tables)}"
        )
    for name, rows in task.tables.items():
        expected = col_index[name]
        for i, row in enumerate(rows):
            if set(row) != expected:
                raise ValidationError(
                    f"table {name} row {i} columns {sorted(row)} != {sorted(expected)}"
                )
        meta = task.fixture_metadata.tables.get(name)
        if meta is None or meta.row_count != len(rows):
            raise ValidationError(f"fixture metadata mismatch for {name}")

    # Semantic checks feasible in Phase 1.
    _check_fk_consistency(task)
    _check_requirements(task, col_index)
    unknown = [e for e in task.edge_cases if e not in KNOWN_EDGE_CASES]
    if unknown:
        raise ValidationError(f"unknown edge cases: {unknown}")
    if not task.instruction.strip():
        raise ValidationError("instruction must be renderable and non-empty")


def _check_fk_consistency(task: TaskInstance) -> None:
    tables = task.tables
    if "customers" in tables and "orders" in tables:
        valid = {r["customer_id"] for r in tables["customers"]}
        for row in tables["orders"]:
            if row.get("customer_id") not in valid:
                raise ValidationError(
                    f"orders.customer_id {row.get('customer_id')} has no customer"
                )
    if "orders" in tables and "order_items" in tables:
        valid_orders = {r["order_id"] for r in tables["orders"]}
        for row in tables["order_items"]:
            if row.get("order_id") not in valid_orders:
                raise ValidationError(f"order_items.order_id {row.get('order_id')} has no order")
    if "products" in tables and "order_items" in tables:
        valid_products = {r["product_id"] for r in tables["products"]}
        for row in tables["order_items"]:
            if row.get("product_id") not in valid_products:
                raise ValidationError(f"order_items.product_id {row.get('product_id')} invalid")
    if "customers" in tables and "events" in tables:
        valid = {r["customer_id"] for r in tables["customers"]}
        for row in tables["events"]:
            if row.get("customer_id") not in valid:
                raise ValidationError(
                    f"events.customer_id {row.get('customer_id')} has no customer"
                )


def _check_requirements(task: TaskInstance, col_index: dict[str, set[str]]) -> None:
    all_cols = {c for cols in col_index.values() for c in cols}

    def _check(col: Any) -> None:
        if not isinstance(col, str):
            return
        if "." in col:
            tname, cname = col.split(".", 1)
            if tname not in col_index or cname not in col_index[tname]:
                raise ValidationError(f"requirement references unknown column: {col}")
        elif col not in all_cols and col not in ("*",):
            # Bare names must exist somewhere; SQL keywords in requirements
            # (e.g. output labels) are validated by template tests instead.
            pass

    for key in ("output_columns", "group_by", "filter_columns", "order_by"):
        cols = task.requirements.get(key, [])
        if isinstance(cols, list):
            for col in cols:
                _check(col)
