"""Cross-run novelty evidence for production-pool expansion.

Compares new Golden records against an existing pool (e.g.
Production-001) along exact, semantic, structural, task, schema, and
edge-combination axes. Produces evidence metrics only: nothing here
rejects a record (quality gates own that) and nothing here scores the
dataset. Deterministic, stdlib only.
"""

from __future__ import annotations

from typing import Any

from .diversity import normalize_sql, schema_fingerprint, sql_features
from .models import PRODUCT_SCHEMA_VERSION, NoveltyReport

__all__ = ["compute_novelty", "edge_combination_key", "structural_signature"]


def structural_signature(sql: str) -> str:
    """Deterministic structural signature from normalized SQL features."""
    features = sql_features(sql)
    parts = [
        f"j{features['join_count']}:{','.join(features['join_types'])}",
        f"g{int(features['group_by'])}h{int(features['having'])}",
        f"c{features['cte_count']}s{features['subquery_count']}w{features['window_over']}",
        f"e{int(features['exists'])}i{int(features['in_subquery'])}d{int(features['distinct'])}",
        f"a{','.join(features['aggregations'])}o{','.join(features['set_ops'])}",
        f"n{features['nesting_depth']}",
    ]
    return "|".join(parts)


def edge_combination_key(golden: dict[str, Any]) -> str:
    """Deterministic edge-case combination for one Golden record."""
    task = golden.get("task", {}) if isinstance(golden.get("task"), dict) else {}
    edges = task.get("edge_cases", []) if isinstance(task, dict) else []
    return ",".join(sorted(str(e) for e in edges)) if isinstance(edges, list) else ""


def compute_novelty(
    *,
    new_golden: list[dict[str, Any]],
    pool_golden: list[dict[str, Any]],
    pool_semantic_groups: set[str] | None = None,
) -> NoveltyReport:
    """Score new records for novelty against the pool (evidence only)."""
    pool_semantic_groups = pool_semantic_groups or set()
    pool_sql = {normalize_sql(str(g.get("candidate_solution", ""))) for g in pool_golden}
    pool_structures = {
        structural_signature(str(g.get("candidate_solution", ""))) for g in pool_golden
    }
    pool_tasks = {
        str(g.get("task", {}).get("task_id", g.get("candidate_id")))
        if isinstance(g.get("task"), dict)
        else str(g.get("candidate_id"))
        for g in pool_golden
    }
    pool_schemas = {schema_fingerprint(g.get("schema")) for g in pool_golden}
    pool_edges = {edge_combination_key(g) for g in pool_golden}

    exact = semantic = structural = 0
    novel_ids: list[str] = []
    novel_tasks: set[str] = set()
    novel_structures: set[str] = set()
    novel_schemas: set[str] = set()
    novel_edges: set[str] = set()
    for golden in sorted(new_golden, key=lambda g: str(g.get("candidate_id", ""))):
        candidate_id = str(golden.get("candidate_id", ""))
        sql = normalize_sql(str(golden.get("candidate_solution", "")))
        structure = structural_signature(str(golden.get("candidate_solution", "")))
        task = golden.get("task", {})
        task_id = str(task.get("task_id", candidate_id) if isinstance(task, dict) else candidate_id)
        schema = schema_fingerprint(golden.get("schema"))
        edges = edge_combination_key(golden)
        quality = golden.get("quality", {}) if isinstance(golden.get("quality"), dict) else {}
        semantic_group = quality.get("semantic_duplicate_group")

        hit = False
        if sql in pool_sql:
            exact += 1
            hit = True
        if semantic_group and str(semantic_group) in pool_semantic_groups:
            semantic += 1
            hit = True
        if structure in pool_structures:
            structural += 1
            hit = True
        if not hit:
            novel_ids.append(candidate_id)
        if task_id not in pool_tasks:
            novel_tasks.add(task_id)
        if structure not in pool_structures:
            novel_structures.add(structure)
        if schema not in pool_schemas:
            novel_schemas.add(schema)
        if edges not in pool_edges:
            novel_edges.add(edges)

    return NoveltyReport(
        new_total=len(new_golden),
        pool_total=len(pool_golden),
        exact_duplicates=exact,
        semantic_duplicates=semantic,
        structural_near_duplicates=structural,
        novel_golden=len(novel_ids),
        novel_tasks=len(novel_tasks),
        novel_sql_structures=len(novel_structures),
        novel_schemas=len(novel_schemas),
        novel_edge_combinations=len(novel_edges),
        novel_ids=sorted(novel_ids),
        schema_version=PRODUCT_SCHEMA_VERSION,
    )
