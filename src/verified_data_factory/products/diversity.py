"""Deterministic dataset-level diversity evidence (§7 remediation).

Compact counts, uniques, ratios, and concentration indicators over
instructions, tasks, SQL structure, schemas, and edge cases. No ML, no
embeddings, no aggregate quality scores — evidence metrics only.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any

from .models import PRODUCT_SCHEMA_VERSION, DiversityReport

__all__ = [
    "build_diversity_report",
    "max_paren_depth",
    "normalize_instruction",
    "normalize_sql",
    "schema_fingerprint",
    "sql_features",
    "table_count",
]

_AGGREGATIONS = ("SUM", "AVG", "COUNT", "MIN", "MAX")
_WINDOW_FUNCS = ("ROW_NUMBER", "RANK", "DENSE_RANK", "LAG", "LEAD")
_SET_OPS = ("UNION", "INTERSECT", "EXCEPT")
_JOIN_TYPES = ("INNER", "LEFT", "RIGHT", "FULL", "CROSS")


def normalize_instruction(text: str) -> str:
    """Deterministic normalization for counting (analysis only)."""
    return re.sub(r"\s+", " ", text.strip().lower())


def normalize_sql(sql: str) -> str:
    """Deterministic normalization for counting (records never altered)."""
    return re.sub(r"\s+", " ", sql.strip().upper())


def max_paren_depth(sql: str) -> int:
    depth = highest = 0
    for char in sql:
        if char == "(":
            depth += 1
            highest = max(highest, depth)
        elif char == ")":
            depth = max(0, depth - 1)
    return highest


def sql_features(sql: str) -> dict[str, Any]:
    """Deterministic structural features of one SQL string."""
    upper = normalize_sql(sql)
    joins = re.findall(r"\b(INNER|LEFT|RIGHT|FULL|CROSS)?\s*(OUTER\s+)?JOIN\b", upper)
    return {
        "join_count": len(re.findall(r"\bJOIN\b", upper)),
        "join_types": sorted({j[0] or "PLAIN" for j in joins if j[0] in _JOIN_TYPES or not j[0]}),
        "group_by": bool(re.search(r"\bGROUP\s+BY\b", upper)),
        "having": bool(re.search(r"\bHAVING\b", upper)),
        "cte_count": len(re.findall(r"\bWITH\b", upper)),
        "subquery_count": len(re.findall(r"\(\s*SELECT\b", upper)),
        "window_over": len(re.findall(r"\bOVER\b", upper)),
        "partition_by": bool(re.search(r"\bPARTITION\s+BY\b", upper)),
        "window_funcs": sorted({f for f in _WINDOW_FUNCS if re.search(rf"\b{f}\b", upper)}),
        "exists": bool(re.search(r"\bEXISTS\b", upper)),
        "in_subquery": bool(re.search(r"\bIN\s*\(", upper)),
        "aggregations": sorted({a for a in _AGGREGATIONS if re.search(rf"\b{a}\b", upper)}),
        "set_ops": sorted({s for s in _SET_OPS if re.search(rf"\b{s}\b", upper)}),
        "distinct": bool(re.search(r"\bDISTINCT\b", upper)),
        "temporal": bool(
            re.search(r"\b(DATE|TIMESTAMP|INTERVAL|STRFTIME|EXTRACT|DATE_TRUNC)\b", upper)
        ),
        "nesting_depth": max_paren_depth(upper),
    }


def schema_fingerprint(schema: Any) -> str:
    """Deterministic identity for a schema payload."""
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def table_count(schema: Any) -> int:
    if isinstance(schema, list):
        return len(schema)
    if isinstance(schema, dict):
        tables = schema.get("tables", schema)
        return len(tables) if isinstance(tables, (list, dict)) else 0
    return 0


def build_diversity_report(
    *,
    golden_records: list[dict[str, Any]],
    quality_by_id: dict[str, dict[str, Any]] | None = None,
    duplicates: dict[str, Any] | None = None,
) -> DiversityReport:
    """Assemble diversity evidence over Golden records (deterministic)."""
    quality_by_id = quality_by_id or {}
    duplicates = duplicates or {}
    n = len(golden_records)

    instructions = [str(g.get("instruction", "")) for g in golden_records]
    normalized_instructions = [normalize_instruction(t) for t in instructions]
    instruction_counts = Counter(normalized_instructions)
    top_samples = [
        {"instruction_prefix": text[:80], "count": count}
        for text, count in instruction_counts.most_common(5)
    ]

    sql_texts = [str(g.get("candidate_solution", "")) for g in golden_records]
    normalized_sql = [normalize_sql(s) for s in sql_texts]
    feature_rows = [sql_features(s) for s in sql_texts]
    feature_presence: dict[str, dict[str, Any]] = {}
    boolean_features = (
        "group_by",
        "having",
        "exists",
        "in_subquery",
        "distinct",
        "temporal",
        "partition_by",
    )
    count_features = ("join_count", "cte_count", "subquery_count", "window_over", "nesting_depth")
    for name in boolean_features:
        present = sum(1 for row in feature_rows if row[name])
        feature_presence[name] = {"records_with_feature": present}
    for name in count_features:
        values = [int(row[name]) for row in feature_rows]
        feature_presence[name] = {
            "records_with_feature": sum(1 for v in values if v > 0),
            "max": max(values) if values else 0,
        }
    for name in ("join_types", "window_funcs", "aggregations", "set_ops"):
        merged: Counter[str] = Counter()
        for row in feature_rows:
            merged.update(row[name])
        feature_presence[name] = {"value_counts": dict(sorted(merged.items()))}

    family_features: dict[str, dict[str, int]] = {}
    for golden, row in zip(golden_records, feature_rows):
        family = str(
            golden.get("task", {}).get("family", "unknown")
            if isinstance(golden.get("task"), dict)
            else "unknown"
        )
        bucket = family_features.setdefault(family, {})
        for name in (*boolean_features, *count_features):
            value = row[name]
            bucket[name] = bucket.get(name, 0) + (
                int(bool(value)) if isinstance(value, bool) else int(value > 0)
            )

    schemas = [g.get("schema") for g in golden_records]
    schema_ids = [schema_fingerprint(s) for s in schemas]
    table_histogram: Counter[str] = Counter()
    for schema in schemas:
        table_histogram[str(table_count(schema))] += 1

    edge_counts: Counter[str] = Counter()
    for golden in golden_records:
        task = golden.get("task", {})
        edges = task.get("edge_cases", []) if isinstance(task, dict) else []
        for edge in edges if isinstance(edges, list) else []:
            edge_counts[str(edge)] += 1
        quality = quality_by_id.get(str(golden.get("candidate_id", "")), {})
        for edge, present in (quality.get("diversity_features", {}) or {}).items():
            if present:
                edge_counts[f"quality:{edge}"] += 1

    groups = duplicates.get("groups", []) if isinstance(duplicates.get("groups"), list) else []
    semantic = [g for g in groups if isinstance(g, dict) and g.get("duplicate_type") == "SEMANTIC"]
    exact = [g for g in groups if isinstance(g, dict) and g.get("duplicate_type") == "EXACT"]
    semantic_sizes = [len(g.get("member_ids", [])) for g in semantic]
    if not semantic:
        # Fall back to per-record group fields when no group list is supplied.
        by_group: dict[str, list[str]] = {}
        for golden in golden_records:
            quality = quality_by_id.get(str(golden.get("candidate_id", "")), {})
            group = quality.get("semantic_duplicate_group")
            if group:
                by_group.setdefault(str(group), []).append(str(golden.get("candidate_id", "")))
        multi = {g: members for g, members in by_group.items() if len(members) > 1}
        semantic_sizes = [len(members) for members in multi.values()]
        semantic_count = len(multi)
    else:
        semantic_count = len(semantic)
    if not exact:
        by_exact: dict[str, list[str]] = {}
        for golden in golden_records:
            quality = quality_by_id.get(str(golden.get("candidate_id", "")), {})
            group = quality.get("exact_duplicate_group")
            if group:
                by_exact.setdefault(str(group), []).append(str(golden.get("candidate_id", "")))
        exact_count = sum(1 for members in by_exact.values() if len(members) > 1)
    else:
        exact_count = len(exact)

    templates: Counter[str] = Counter()
    for golden in golden_records:
        task = golden.get("task", {})
        template = task.get("template_id", "unknown") if isinstance(task, dict) else "unknown"
        templates[str(template)] += 1

    unique_instructions = len(set(normalized_instructions))
    unique_sql = len(set(normalized_sql))
    top1 = instruction_counts.most_common(1)[0][1] if instruction_counts else 0
    top5 = sum(c for _, c in instruction_counts.most_common(5))
    return DiversityReport(
        record_count=n,
        instruction_unique_normalized=unique_instructions,
        instruction_unique_ratio=(unique_instructions / n) if n else None,
        instruction_top_share=(top1 / n) if n else None,
        instruction_top5_share=(top5 / n) if n else None,
        instruction_top_samples=top_samples,
        task_unique_count=len(
            {
                str(g.get("task", {}).get("task_id", g.get("candidate_id")))
                if isinstance(g.get("task"), dict)
                else str(g.get("candidate_id"))
                for g in golden_records
            }
        ),
        template_counts=dict(sorted(templates.items())),
        semantic_groups=semantic_count,
        semantic_largest_group=max(semantic_sizes) if semantic_sizes else 0,
        exact_groups=exact_count,
        sql_features=feature_presence,
        sql_family_features={
            f: dict(sorted(v.items())) for f, v in sorted(family_features.items())
        },
        sql_unique_normalized=unique_sql,
        sql_unique_ratio=(unique_sql / n) if n else None,
        schema_identities=len(set(schema_ids)),
        schema_table_histogram=dict(sorted(table_histogram.items())),
        edge_counts=dict(sorted(edge_counts.items())),
        schema_version=PRODUCT_SCHEMA_VERSION,
    )
