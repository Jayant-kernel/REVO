"""Coverage analysis (Phase 5).

Answers which capabilities and edge cases the dataset represents, with
counts, rates, and explicit uncovered lists. Taxonomies are fixed and
documented; detectors are deterministic keyword scans over normalized SQL.
"""

from __future__ import annotations

from .duplicate_detection import normalize_sql
from .models import CoverageReport, RecordQuality
from .task_quality import known_edge_cases

SQL_CONSTRUCTS: tuple[str, ...] = (
    "select",
    "join",
    "group-by",
    "having",
    "cte",
    "subquery",
    "window",
    "case",
    "exists",
    "date-fn",
    "aggregation",
    "filtering",
    "order-by",
    "distinct",
    "union",
    "limit",
)

_CONSTRUCT_PATTERNS: dict[str, str] = {
    "select": r"\bSELECT\b",
    "join": r"\bJOIN\b",
    "group-by": r"\bGROUP\s+BY\b",
    "having": r"\bHAVING\b",
    "cte": r"\bWITH\b",
    "subquery": r"\(\s*SELECT\b",
    "window": r"\bOVER\b|\bRANK\s*\(|\bROW_NUMBER\s*\(|\bLAG\s*\(|\bLEAD\s*\(",
    "case": r"\bCASE\b",
    "exists": r"\bEXISTS\b",
    "date-fn": r"\bDATE\s*\(|STRFTIME|INTERVAL|DATE_TRUNC",
    "aggregation": r"\bSUM\s*\(|\bAVG\s*\(|\bCOUNT\s*\(|\bMIN\s*\(|\bMAX\s*\(",
    "filtering": r"\bWHERE\b",
    "order-by": r"\bORDER\s+BY\b",
    "distinct": r"\bDISTINCT\b",
    "union": r"\bUNION\b",
    "limit": r"\bLIMIT\b",
}

FAMILIES: tuple[str, ...] = (
    "simple_joins",
    "multi_joins",
    "aggregation",
    "cte",
    "subqueries",
    "window_functions",
    "temporal",
    "deduplication",
    "retention",
    "funnel",
)


def detect_constructs(sql: str) -> set[str]:
    """SQL constructs present in one query (normalized, deterministic)."""
    import re

    normalized = f" {normalize_sql(sql)} "
    return {name for name, pattern in _CONSTRUCT_PATTERNS.items() if re.search(pattern, normalized)}


def compute_coverage(
    qualities: list[RecordQuality], candidate_sql: dict[str, str]
) -> CoverageReport:
    """Coverage over families, constructs, and edge cases with uncovered lists."""
    families = sorted({q.family for q in qualities})
    constructs: set[str] = set()
    for quality in qualities:
        constructs |= detect_constructs(candidate_sql[quality.candidate_id])
    edges: set[str] = set()
    for quality in qualities:
        edges |= set(quality.task_quality.edge_cases_present)
    known_edges = sorted(known_edge_cases())
    uncovered_families = [f for f in FAMILIES if f not in families]
    uncovered_constructs = [c for c in SQL_CONSTRUCTS if c not in constructs]
    uncovered_edges = [e for e in known_edges if e not in edges]
    return CoverageReport(
        families_covered=families,
        families_total=len(FAMILIES),
        family_coverage_rate=len(families) / len(FAMILIES),
        constructs_covered=sorted(constructs),
        constructs_total=len(SQL_CONSTRUCTS),
        construct_coverage_rate=len(constructs) / len(SQL_CONSTRUCTS),
        edge_cases_covered=sorted(edges),
        edge_cases_total=len(known_edges),
        edge_case_coverage_rate=len(edges) / len(known_edges) if known_edges else 1.0,
        uncovered_families=uncovered_families,
        uncovered_constructs=uncovered_constructs,
        uncovered_edge_cases=uncovered_edges,
    )
