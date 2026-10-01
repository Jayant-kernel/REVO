"""Dataset-independent task-quality checks (Phase 5).

Reuses the Task Engine's own validation (`validate_task`,
`SEMANTIC_REQUIREMENTS`) instead of recreating semantics. Ambiguity
signals are deterministic structural/textual checks — heuristic flags,
never judgments, and never an LLM.
"""

from __future__ import annotations

from verified_data_factory.task_engine.models import TaskInstance
from verified_data_factory.task_engine.validation import RELEASE_EDGE_CASES, SEMANTIC_REQUIREMENTS

from .models import TaskQualityEvidence

# Expected edge cases per family, derived from the Phase 1 template
# declarations (see templates/sql/*) and docs/task-semantics.md.
FAMILY_EDGE_CASES: dict[str, frozenset[str]] = {
    "simple_joins": frozenset({"missing_relationships", "null_values"}),
    "multi_joins": frozenset({"missing_relationships", "multiple_matching_rows"}),
    "aggregation": frozenset({"null_values", "single_row_groups", "zero_values"}),
    "cte": frozenset({"missing_relationships"}),
    "subqueries": frozenset({"missing_relationships"}),
    "window_functions": frozenset({"ties", "null_values"}),
    "temporal": frozenset({"out_of_order_timestamps", "same_day_events"}),
    "deduplication": frozenset({"duplicates", "duplicate_events", "ties"}),
    "retention": frozenset(
        {"no_events", "duplicate_events", "multiple_purchases", "same_day_events"}
    ),
    "funnel": frozenset({"missing_relationships", "out_of_order_timestamps", "duplicate_events"}),
}

# Families whose spec must pin tie behavior explicitly.
TIE_SEMANTIC_FAMILIES = frozenset({"deduplication", "window_functions", "cte"})

HEDGE_WORDS = frozenset(
    {
        "appropriate",
        "relevant",
        "etc.",
        "as needed",
        "reasonable",
        "proper",
        "suitable",
        "maybe",
        "possibly",
    }
)


def assess_task_quality(task: TaskInstance) -> TaskQualityEvidence:
    """Assess one task without any dataset context."""
    from verified_data_factory.task_engine import validate_task

    errors: list[str] = []
    try:
        validate_task(task)
    except Exception as exc:  # noqa: BLE001 — validation failures are evidence
        errors.append(f"{type(exc).__name__}: {exc}")

    required = sorted(SEMANTIC_REQUIREMENTS.get(task.family, frozenset()))
    present = sorted(k for k in required if k in task.requirements)
    semantic_rate = len(present) / len(required) if required else 1.0
    if task.family not in SEMANTIC_REQUIREMENTS:
        errors.append(f"unknown family {task.family!r}")

    ambiguity = _detect_ambiguity(task)
    expected = sorted(FAMILY_EDGE_CASES.get(task.family, frozenset()))
    expected_present = set(expected) & set(task.edge_cases)
    present_edges = sorted(set(task.edge_cases) & RELEASE_EDGE_CASES)
    edge_rate = len(expected_present) / len(expected) if expected else 1.0

    schema_ok, schema_issues = _check_schema_consistency(task)
    instr_ok, instr_issues = _check_instruction_consistency(task)

    return TaskQualityEvidence(
        valid=not errors,
        validation_errors=errors,
        semantic_required=required,
        semantic_present=present,
        semantic_completeness_rate=semantic_rate,
        ambiguity_flags=ambiguity,
        edge_cases_expected=expected,
        edge_cases_present=present_edges,
        edge_case_coverage_rate=edge_rate,
        schema_consistent=schema_ok,
        schema_issues=schema_issues,
        instruction_spec_consistent=instr_ok,
        instruction_issues=instr_issues,
    )


def _detect_ambiguity(task: TaskInstance) -> list[str]:
    flags: list[str] = []
    lowered = task.instruction.lower()
    for hedge in sorted(HEDGE_WORDS):
        if hedge in lowered:
            flags.append(f"hedge-word:{hedge}")
    if task.family in TIE_SEMANTIC_FAMILIES and "tie" not in lowered:
        flags.append("missing-tie-mention")
    if task.requirements.get("order_by") and "order" not in lowered:
        flags.append("missing-order-mention")
    return flags


def _check_schema_consistency(task: TaskInstance) -> tuple[bool, list[str]]:
    issues: list[str] = []
    fixture_tables = set(task.tables)
    schema_tables = {t.name for t in task.schema_}
    if fixture_tables != schema_tables:
        issues.append(f"fixture tables {sorted(fixture_tables)} != schema {sorted(schema_tables)}")
    for table in task.schema_:
        declared = {c.name for c in table.columns}
        for i, row in enumerate(task.tables.get(table.name, [])):
            if set(row) != declared:
                issues.append(f"{table.name} row {i} columns mismatch")
                break
        meta = task.fixture_metadata.tables.get(table.name)
        if meta is None or meta.row_count != len(task.tables.get(table.name, [])):
            issues.append(f"{table.name} metadata row-count mismatch")
    return (not issues, issues)


def _check_instruction_consistency(task: TaskInstance) -> tuple[bool, list[str]]:
    issues: list[str] = []
    lowered = task.instruction.lower()
    for table in task.schema_:
        if table.name.lower() not in lowered:
            issues.append(f"table {table.name!r} not mentioned in instruction")
    for key, value in task.requirements.items():
        if isinstance(value, (int, float)) and str(value) not in task.instruction:
            issues.append(f"requirement {key}={value} not reflected in instruction")
    if not task.instruction.strip():
        issues.append("empty instruction")
    return (not issues, issues)


def known_edge_cases() -> frozenset[str]:
    """The frozen 17-category release coverage denominator."""
    return RELEASE_EDGE_CASES
