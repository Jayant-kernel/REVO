"""Append-only JSONL provenance store (Phase 6, §31 + §33).

Layout under one directory: ``nodes.jsonl``, ``edges.jsonl``,
``activities.jsonl``. Records are immutable history — appending the same
id with identical content is idempotent; the same id with different
content is rejected; nothing is ever overwritten. In-memory indexes make
lineage queries O(edges) without full rescans.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import StoreError
from .models import ProvenanceActivity, ProvenanceEdge, ProvenanceNode


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if line.strip():
                records.append(json.loads(line))
    return records


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")


class ProvenanceStore:
    """Local file-backed provenance graph (no external services)."""

    def __init__(self, directory: str | Path) -> None:
        self._dir = Path(directory)
        self._nodes: dict[str, ProvenanceNode] = {}
        self._edges: dict[str, ProvenanceEdge] = {}
        self._activities: dict[str, ProvenanceActivity] = {}
        self._outgoing: dict[str, list[str]] = {}
        self._incoming: dict[str, list[str]] = {}
        self._load()

    @property
    def directory(self) -> Path:
        return self._dir

    def _load(self) -> None:
        for raw in _read_jsonl(self._dir / "nodes.jsonl"):
            node = ProvenanceNode.model_validate(raw)
            self._nodes[node.node_id] = node
        for raw in _read_jsonl(self._dir / "edges.jsonl"):
            edge = ProvenanceEdge.model_validate(raw)
            self._register_edge(edge)
        for raw in _read_jsonl(self._dir / "activities.jsonl"):
            activity = ProvenanceActivity.model_validate(raw)
            self._activities[activity.run_id] = activity

    def _register_edge(self, edge: ProvenanceEdge) -> None:
        self._edges[edge.edge_id] = edge
        self._outgoing.setdefault(edge.source_id, []).append(edge.edge_id)
        self._incoming.setdefault(edge.target_id, []).append(edge.edge_id)

    def append_node(self, node: ProvenanceNode) -> ProvenanceNode:
        """Append a node; identical re-appends are idempotent, conflicts rejected."""
        existing = self._nodes.get(node.node_id)
        if existing is not None:
            if existing != node:
                raise StoreError(f"node id conflict (same id, different content): {node.node_id}")
            return existing
        self._nodes[node.node_id] = node
        _append_jsonl(self._dir / "nodes.jsonl", node.model_dump(mode="json"))
        return node

    def append_edge(self, edge: ProvenanceEdge) -> ProvenanceEdge:
        """Append an edge; identical re-appends are idempotent."""
        existing = self._edges.get(edge.edge_id)
        if existing is not None:
            if existing != edge:
                raise StoreError(f"edge id conflict: {edge.edge_id}")
            return existing
        if edge.source_id not in self._nodes:
            raise StoreError(f"edge references missing source node: {edge.source_id}")
        if edge.target_id not in self._nodes:
            raise StoreError(f"edge references missing target node: {edge.target_id}")
        self._register_edge(edge)
        _append_jsonl(self._dir / "edges.jsonl", edge.model_dump(mode="json"))
        return edge

    def append_activity(self, activity: ProvenanceActivity) -> ProvenanceActivity:
        """Append an activity; same run id must carry identical content."""
        existing = self._activities.get(activity.run_id)
        if existing is not None:
            if existing != activity:
                raise StoreError(f"activity id conflict: {activity.run_id}")
            return existing
        self._activities[activity.run_id] = activity
        _append_jsonl(self._dir / "activities.jsonl", activity.model_dump(mode="json"))
        return activity

    def get_node(self, node_id: str) -> ProvenanceNode | None:
        return self._nodes.get(node_id)

    def get_run(self, run_id: str) -> ProvenanceActivity | None:
        return self._activities.get(run_id)

    def nodes(self) -> dict[str, ProvenanceNode]:
        return dict(self._nodes)

    def edges(self) -> list[ProvenanceEdge]:
        return list(self._edges.values())

    def lineage(self, node_id: str, direction: str = "both") -> dict[str, list[str]]:
        """BFS lineage: predecessors (``up``), successors (``down``), or both."""
        if direction not in ("up", "down", "both"):
            raise StoreError(f"invalid lineage direction: {direction!r}")
        result: dict[str, list[str]] = {"up": [], "down": []}
        if direction in ("up", "both"):
            seen, frontier = {node_id}, [node_id]
            while frontier:
                current = frontier.pop()
                for edge_id in self._incoming.get(current, []):
                    parent = self._edges[edge_id].source_id
                    if parent not in seen:
                        seen.add(parent)
                        result["up"].append(parent)
                        frontier.append(parent)
        if direction in ("down", "both"):
            seen, frontier = {node_id}, [node_id]
            while frontier:
                current = frontier.pop()
                for edge_id in self._outgoing.get(current, []):
                    child = self._edges[edge_id].target_id
                    if child not in seen:
                        seen.add(child)
                        result["down"].append(child)
                        frontier.append(child)
        return result

    def validate_references(self) -> list[str]:
        """Every edge endpoint must resolve to a stored node."""
        problems = []
        for edge in self._edges.values():
            if edge.source_id not in self._nodes:
                problems.append(f"edge {edge.edge_id} references missing source {edge.source_id}")
            if edge.target_id not in self._nodes:
                problems.append(f"edge {edge.edge_id} references missing target {edge.target_id}")
        return problems

    def export_graph(self) -> dict[str, Any]:
        """Full graph as plain data (nodes/edges/activities, sorted)."""
        return {
            "nodes": [
                n.model_dump(mode="json")
                for n in sorted(self._nodes.values(), key=lambda n: n.node_id)
            ],
            "edges": [
                e.model_dump(mode="json")
                for e in sorted(self._edges.values(), key=lambda e: e.edge_id)
            ],
            "activities": [
                a.model_dump(mode="json")
                for a in sorted(self._activities.values(), key=lambda a: a.run_id)
            ],
        }

    def counts(self) -> dict[str, int]:
        return {
            "nodes": len(self._nodes),
            "edges": len(self._edges),
            "activities": len(self._activities),
        }
