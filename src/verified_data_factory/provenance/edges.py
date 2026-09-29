"""Lineage edges and graph validation (Phase 6, §11 + §32).

Edges are deterministic: ``edge_id = sha256(source|relationship|target)``.
Validation enforces the relationship vocabulary, reference integrity,
duplicate-ID conflicts, orphan detection, direction rules, and acyclicity
(all Phase 6 relations are DAG relations).
"""

from __future__ import annotations

import hashlib
from typing import get_args

from .errors import StoreError
from .models import PROVENANCE_SCHEMA_VERSION, EdgeType, NodeType, ProvenanceEdge, ProvenanceNode

_RELATIONSHIPS: frozenset[str] = frozenset(get_args(EdgeType))

# Allowed (source_type, relationship, target_type) triples. Read as:
# "source <RELATIONSHIP> target", e.g. CANDIDATE_SOLUTION EXECUTED_BY EXECUTION_RUN.
_ALLOWED: set[tuple[str, str, str]] = {
    ("TASK_INSTANCE", "DERIVED_FROM", "TASK_TEMPLATE"),
    ("TASK_INSTANCE", "GENERATED_BY", "GENERATION_RUN"),
    ("GENERATION_RUN", "DERIVED_FROM", "CANDIDATE_SOLUTION"),
    ("CANDIDATE_SOLUTION", "EXECUTED_BY", "EXECUTION_RUN"),
    ("EXECUTION_RUN", "DERIVED_FROM", "EXECUTION_RESULT"),
    ("EXECUTION_RESULT", "VERIFIED_BY", "VERIFICATION_RUN"),
    ("VERIFICATION_RUN", "DERIVED_FROM", "VERIFICATION_RESULT"),
    ("VERIFICATION_RESULT", "QUALIFIED_BY", "QUALITY_RUN"),
    ("QUALITY_RUN", "DERIVED_FROM", "RECORD_QUALITY"),
    ("RECORD_QUALITY", "AUDITED_BY", "AUDIT_SAMPLE"),
    ("AUDIT_SAMPLE", "DERIVED_FROM", "AUDIT_RESULT"),
    ("RECORD_QUALITY", "SELECTED_BY", "GOLDEN_SELECTION"),
    ("GOLDEN_SELECTION", "DERIVED_FROM", "GOLDEN_RECORD"),
    ("GOLDEN_RECORD", "INCLUDED_IN", "DATASET_SNAPSHOT"),
    ("GOLDEN_RECORD", "EXPORTED_AS", "ARTIFACT"),
    ("DATASET_SNAPSHOT", "EXPORTED_AS", "ARTIFACT"),
    ("TASK_INSTANCE", "USES_CONFIGURATION", "CONFIGURATION"),
    ("GENERATION_RUN", "USES_CONFIGURATION", "CONFIGURATION"),
    ("GENERATION_RUN", "USES_MODEL", "MODEL_SNAPSHOT"),
    ("EXECUTION_RUN", "USES_CONFIGURATION", "CONFIGURATION"),
    ("EXECUTION_RUN", "USES_ENVIRONMENT", "ENVIRONMENT_SNAPSHOT"),
    ("VERIFICATION_RUN", "USES_CONFIGURATION", "CONFIGURATION"),
    ("QUALITY_RUN", "USES_CONFIGURATION", "CONFIGURATION"),
    ("GOLDEN_SELECTION", "USES_CONFIGURATION", "CONFIGURATION"),
    ("TASK_INSTANCE", "USES_ARTIFACT", "ARTIFACT"),
    ("CANDIDATE_SOLUTION", "USES_ARTIFACT", "ARTIFACT"),
    ("EXECUTION_RESULT", "USES_ARTIFACT", "ARTIFACT"),
    ("VERIFICATION_RESULT", "USES_ARTIFACT", "ARTIFACT"),
    ("RECORD_QUALITY", "USES_ARTIFACT", "ARTIFACT"),
    ("GOLDEN_RECORD", "USES_ARTIFACT", "ARTIFACT"),
    ("GENERATION_RUN", "USES_ENVIRONMENT", "ENVIRONMENT_SNAPSHOT"),
    ("VERIFICATION_RUN", "USES_ENVIRONMENT", "ENVIRONMENT_SNAPSHOT"),
    ("TASK_TEMPLATE", "DERIVED_FROM", "SOURCE_SNAPSHOT"),
    ("RECORD_QUALITY", "SUPERSEDES", "RECORD_QUALITY"),
    ("GOLDEN_RECORD", "SUPERSEDES", "GOLDEN_RECORD"),
}


def edge_id(source_id: str, relationship: str, target_id: str) -> str:
    """Deterministic edge identity (idempotent re-appends allowed)."""
    return (
        "sha256:" + hashlib.sha256(f"{source_id}|{relationship}|{target_id}".encode()).hexdigest()
    )


def make_edge(source_id: str, relationship: EdgeType, target_id: str) -> ProvenanceEdge:
    """Build a validated edge (relationship vocabulary enforced)."""
    if relationship not in _RELATIONSHIPS:
        raise StoreError(f"unknown relationship: {relationship!r}")
    return ProvenanceEdge(
        edge_id=edge_id(source_id, relationship, target_id),
        source_id=source_id,
        target_id=target_id,
        relationship=relationship,
        schema_version=PROVENANCE_SCHEMA_VERSION,
    )


def validate_edge_types(edges: list[ProvenanceEdge], nodes: dict[str, ProvenanceNode]) -> list[str]:
    """Direction/type rule violations (unknown node refs reported separately)."""
    problems: list[str] = []
    for edge in edges:
        source = nodes.get(edge.source_id)
        target = nodes.get(edge.target_id)
        if source is None or target is None:
            continue
        triple = (source.node_type, edge.relationship, target.node_type)
        if triple not in _ALLOWED:
            problems.append(
                f"forbidden direction: {source.node_type} {edge.relationship} {target.node_type}"
            )
    return problems


def find_cycles(edges: list[ProvenanceEdge]) -> list[list[str]]:
    """Detect directed cycles (all relations here must form a DAG)."""
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source_id, []).append(edge.target_id)
    visited: dict[str, int] = {}
    cycles: list[list[str]] = []

    def visit(node: str, stack: list[str]) -> None:
        visited[node] = 1
        stack.append(node)
        for nxt in adjacency.get(node, []):
            state = visited.get(nxt, 0)
            if state == 1:
                cycles.append(stack[stack.index(nxt) :] + [nxt])
            elif state == 0:
                visit(nxt, stack)
        stack.pop()
        visited[node] = 2

    for start in adjacency:
        if visited.get(start, 0) == 0:
            visit(start, [])
    return cycles


def validate_graph(nodes: dict[str, ProvenanceNode], edges: list[ProvenanceEdge]) -> list[str]:
    """Reference integrity + direction + acyclicity diagnostics."""
    problems: list[str] = []
    for edge in edges:
        if edge.source_id not in nodes:
            problems.append(f"missing referenced node: {edge.source_id}")
        if edge.target_id not in nodes:
            problems.append(f"missing referenced node: {edge.target_id}")
    problems.extend(validate_edge_types(edges, nodes))
    for cycle in find_cycles(edges):
        problems.append(f"cycle detected: {' -> '.join(cycle)}")
    return problems


def orphans(
    nodes: dict[str, ProvenanceNode],
    edges: list[ProvenanceEdge],
    root_types: set[NodeType] | None = None,
) -> list[str]:
    """Nodes with no incident edges, excluding accepted roots."""
    roots = root_types or {
        "TASK_TEMPLATE",
        "SOURCE_SNAPSHOT",
        "ENVIRONMENT_SNAPSHOT",
        "MODEL_SNAPSHOT",
        "CONFIGURATION",
    }
    touched: set[str] = set()
    for edge in edges:
        touched.add(edge.source_id)
        touched.add(edge.target_id)
    return sorted(
        node_id
        for node_id, node in nodes.items()
        if node_id not in touched and node.node_type not in roots
    )
