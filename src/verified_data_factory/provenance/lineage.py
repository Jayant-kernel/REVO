"""Lineage graph construction and tracing (Phase 6).

``build_provenance`` wires one deterministic graph over Phase 1–5 outputs:
nodes for every entity, edges for every lineage fact, shared snapshots
(source/environment/model/configs/selection) linked by reference. One
``ProvenanceActivity`` per stage records the operational side. Nothing
here re-runs generation, execution, verification, or quality logic.
"""

from __future__ import annotations

import logging
from typing import Any

from verified_data_factory.quality.models import (
    AuditSample,
    GoldenRecord,
    RecordQuality,
    VerifiedRecord,
)

from . import nodes as node_builders
from .activities import finish_activity, snapshot_config, start_activity
from .artifacts import artifact_from_bytes, record_artifact
from .edges import make_edge
from .hashing import hash_bytes
from .models import (
    ActivityType,
    ArtifactRef,
    ProvenanceActivity,
    ProvenanceEdge,
    ProvenanceNode,
)

logger = logging.getLogger(__name__)


class BuiltProvenance:
    """Assembled graph plus side registries (plain container)."""

    def __init__(
        self,
        nodes: dict[str, ProvenanceNode],
        edges: list[ProvenanceEdge],
        activities: list[ProvenanceActivity],
        artifacts: list[ArtifactRef],
    ) -> None:
        self.nodes = nodes
        self.edges = edges
        self.activities = activities
        self.artifacts = artifacts


class _Graph:
    def __init__(self) -> None:
        self.nodes: dict[str, ProvenanceNode] = {}
        self.edges: list[ProvenanceEdge] = []
        self.activities: list[ProvenanceActivity] = []
        self.artifacts: list[ArtifactRef] = []

    def add_node(self, node: ProvenanceNode) -> ProvenanceNode:
        existing = self.nodes.get(node.node_id)
        if existing is not None and existing != node:
            from .errors import StoreError

            raise StoreError(f"conflicting node content for id: {node.node_id}")
        self.nodes[node.node_id] = node
        return node

    def add_edge(self, source_id: str, relationship: Any, target_id: str) -> None:
        edge = make_edge(source_id, relationship, target_id)
        if edge.edge_id not in {e.edge_id for e in self.edges}:
            if source_id not in self.nodes or target_id not in self.nodes:
                from .errors import StoreError

                raise StoreError(f"edge references unknown node: {edge.edge_id}")
            self.edges.append(edge)

    def add_activity(self, activity: ProvenanceActivity) -> None:
        self.activities.append(activity)

    def add_artifact(self, artifact: ArtifactRef) -> None:
        self.artifacts.append(artifact)


def build_provenance(
    records: list[VerifiedRecord],
    qualities: list[RecordQuality],
    golden_records: list[GoldenRecord],
    audit_sample: AuditSample | None,
    quality_config: dict[str, Any],
    verification_config: dict[str, Any] | None,
    factory_version: str,
    source: Any | None = None,
    environment: Any | None = None,
    selection_config_id: str | None = None,
) -> BuiltProvenance:
    """Wire the full TaskInstance → GoldenRecord graph (deterministic).

    ``source``/``environment`` accept ``*_snapshot`` model instances (or
    None, in which case those links are simply absent and completeness
    reports them). ``selection_config_id`` overrides the derived default.
    """

    graph = _Graph()
    quality_by_id = {q.candidate_id: q for q in qualities}
    golden_by_id = {g.candidate_id: g for g in golden_records}
    audit_by_id = {}
    if audit_sample is not None:
        for item in audit_sample.items:
            audit_by_id[item.candidate_id] = item

    # Shared snapshots and selection context (one node each, referenced).
    if source is not None:
        graph.add_node(_snapshot_node(source, "SOURCE_SNAPSHOT"))
    if environment is not None:
        graph.add_node(_snapshot_node(environment, "ENVIRONMENT_SNAPSHOT"))
    quality_config_node = _config_node("quality", quality_config, "1.0")
    graph.add_node(quality_config_node)
    verification_config_node = None
    if verification_config is not None:
        verification_config_node = _config_node("verification", verification_config, "1.0")
        graph.add_node(verification_config_node)
    selection_id = selection_config_id or quality_config_node.node_id.replace("sha256:", "cfg-", 1)
    golden_selection = node_builders.make_node(
        "GOLDEN_SELECTION",
        {
            "selection_config_id": selection_id,
            "quality_config_version": quality_config.get("config_version", "1.0"),
            "quality_engine_version": quality_config.get("quality_engine_version", "1.0"),
            "factory_version": factory_version,
        },
    )
    graph.add_node(golden_selection)

    model_cache: dict[str, ProvenanceNode] = {}
    template_cache: dict[str, ProvenanceNode] = {}
    config_cache: dict[str, ProvenanceNode] = {}

    def cached_config(name: str, content: Any, schema_version: str) -> ProvenanceNode:
        """Deduplicate config nodes by content id (same content, one node)."""
        snapshot = snapshot_config(name, content, schema_version)
        cached = config_cache.get(snapshot.configuration_id)
        if cached is not None:
            return cached
        node = ProvenanceNode(
            node_id=snapshot.configuration_id,
            node_type="CONFIGURATION",
            schema_version=snapshot.schema_version,
            payload=snapshot.model_dump(mode="json"),
        )
        config_cache[snapshot.configuration_id] = node
        return graph.add_node(node)

    for record in sorted(records, key=lambda r: r.candidate.candidate_id):
        candidate_id = record.candidate.candidate_id
        quality = quality_by_id.get(candidate_id)

        task_node = graph.add_node(node_builders.task_instance_node(record.task))
        template_key = f"{record.task.template_id}|{record.task.template_version}"
        if template_key not in template_cache:
            template_cache[template_key] = graph.add_node(
                node_builders.make_node(
                    "TASK_TEMPLATE",
                    {
                        "template_id": record.task.template_id,
                        "template_version": record.task.template_version,
                    },
                )
            )
        graph.add_edge(task_node.node_id, "DERIVED_FROM", template_cache[template_key].node_id)
        if source is not None:
            graph.add_edge(
                template_cache[template_key].node_id, "DERIVED_FROM", _snapshot_id(source)
            )

        generation_run = graph.add_node(
            node_builders.make_node(
                "GENERATION_RUN",
                {
                    "task_id": record.task.task_id,
                    "model_snapshot_hint": record.candidate.model,
                    "generation_config": record.candidate.generation_config.model_dump(mode="json"),
                    "prompt_version": record.candidate.prompt_version,
                    "tool_version": record.candidate.generation_schema_version,
                    "factory_version": factory_version,
                },
            )
        )
        graph.add_edge(task_node.node_id, "GENERATED_BY", generation_run.node_id)

        model_key = f"{record.candidate.provider}|{record.candidate.model}|{record.candidate.model_revision}"
        if model_key not in model_cache:
            snapshot = node_builders.capture_model_snapshot(record.candidate)
            model_cache[model_key] = graph.add_node(_snapshot_node(snapshot, "MODEL_SNAPSHOT"))
        graph.add_edge(generation_run.node_id, "USES_MODEL", model_cache[model_key].node_id)
        gen_config_node = cached_config(
            f"generation:{candidate_id}",
            {
                **record.candidate.generation_config.model_dump(mode="json"),
                "prompt_version": record.candidate.prompt_version,
            },
            record.candidate.generation_schema_version,
        )
        graph.add_edge(generation_run.node_id, "USES_CONFIGURATION", gen_config_node.node_id)

        candidate_node = graph.add_node(node_builders.candidate_solution_node(record.candidate))
        graph.add_edge(generation_run.node_id, "DERIVED_FROM", candidate_node.node_id)
        for artifact in _candidate_artifacts(record, candidate_id):
            graph.add_artifact(artifact)
            graph.add_node(_artifact_node(artifact))
            graph.add_edge(candidate_node.node_id, "USES_ARTIFACT", artifact.artifact_id)

        execution_run = graph.add_node(
            node_builders.make_node(
                "EXECUTION_RUN",
                {
                    "candidate_id": candidate_id,
                    "sandbox_image": record.execution.sandbox_image,
                    "sandbox_image_digest": record.execution.sandbox_image_digest,
                    "sandbox_config_version": record.execution.sandbox_config_version,
                    "resource_limits": record.execution.resource_limits.model_dump(mode="json"),
                    "duckdb_version": record.execution.duckdb_version,
                    "tool_version": record.execution.sandbox_config_version,
                    "factory_version": factory_version,
                },
            )
        )
        graph.add_edge(candidate_node.node_id, "EXECUTED_BY", execution_run.node_id)
        sandbox_config_node = cached_config(
            f"sandbox:{candidate_id}",
            {
                **record.execution.resource_limits.model_dump(mode="json"),
                "sandbox_config_version": record.execution.sandbox_config_version,
            },
            record.execution.sandbox_config_version,
        )
        graph.add_edge(execution_run.node_id, "USES_CONFIGURATION", sandbox_config_node.node_id)
        if environment is not None:
            graph.add_edge(execution_run.node_id, "USES_ENVIRONMENT", _snapshot_id(environment))
            graph.add_edge(generation_run.node_id, "USES_ENVIRONMENT", _snapshot_id(environment))

        execution_node = graph.add_node(node_builders.execution_result_node(record.execution))
        graph.add_edge(execution_run.node_id, "DERIVED_FROM", execution_node.node_id)

        verification_run = graph.add_node(
            node_builders.make_node(
                "VERIFICATION_RUN",
                {
                    "task_id": record.task.task_id,
                    "candidate_id": candidate_id,
                    "oracle_version": record.verification.oracle_version,
                    "verification_config_version": record.verification.verification_config_version,
                    "tool_version": record.verification.verification_config_version,
                    "factory_version": factory_version,
                },
            )
        )
        graph.add_edge(execution_node.node_id, "VERIFIED_BY", verification_run.node_id)
        if verification_config_node is not None:
            graph.add_edge(
                verification_run.node_id, "USES_CONFIGURATION", verification_config_node.node_id
            )

        verification_node = graph.add_node(
            node_builders.verification_result_node(record.verification)
        )
        graph.add_edge(verification_run.node_id, "DERIVED_FROM", verification_node.node_id)

        quality_run = graph.add_node(
            node_builders.make_node(
                "QUALITY_RUN",
                {
                    "candidate_id": candidate_id,
                    "quality_config_version": quality_config.get("config_version", "1.0"),
                    "quality_engine_version": quality_config.get("quality_engine_version", "1.0"),
                    "tool_version": quality_config.get("quality_engine_version", "1.0"),
                    "factory_version": factory_version,
                },
            )
        )
        graph.add_edge(verification_node.node_id, "QUALIFIED_BY", quality_run.node_id)
        graph.add_edge(quality_run.node_id, "USES_CONFIGURATION", quality_config_node.node_id)

        if quality is not None:
            quality_node = graph.add_node(node_builders.record_quality_node(quality))
            graph.add_edge(quality_run.node_id, "DERIVED_FROM", quality_node.node_id)
            if candidate_id in audit_by_id and audit_sample is not None:
                audit_nodes = graph.add_node(node_builders.audit_sample_node(audit_sample))
                graph.add_edge(quality_node.node_id, "AUDITED_BY", audit_nodes.node_id)
                item = audit_by_id[candidate_id]
                if item.result is not None:
                    result_node = graph.add_node(
                        node_builders.audit_result_node(candidate_id, item.result, item.note)
                    )
                    graph.add_edge(audit_nodes.node_id, "DERIVED_FROM", result_node.node_id)
            graph.add_edge(quality_node.node_id, "SELECTED_BY", golden_selection.node_id)
            if candidate_id in golden_by_id:
                golden_node = graph.add_node(
                    node_builders.golden_record_node(golden_by_id[candidate_id])
                )
                graph.add_edge(golden_selection.node_id, "DERIVED_FROM", golden_node.node_id)
                golden_bytes = golden_by_id[candidate_id].model_dump_json(by_alias=True).encode()
                golden_artifact = record_artifact(
                    content_hash=hash_bytes(golden_bytes),
                    size_bytes=len(golden_bytes),
                    artifact_type="golden_record",
                    logical_name=f"{candidate_id}.golden.json",
                    relative_locator=f"golden_records/{candidate_id}.golden.json",
                )
                graph.add_artifact(golden_artifact)
                graph.add_node(_artifact_node(golden_artifact))
                graph.add_edge(golden_node.node_id, "USES_ARTIFACT", golden_artifact.artifact_id)

    stage_activities: list[tuple[ActivityType, str]] = [
        ("GENERATION_RUN", "1.0"),
        ("EXECUTION_RUN", "1.0"),
        ("VERIFICATION_RUN", "1.0"),
        ("QUALITY_RUN", "1.0"),
        ("GOLDEN_SELECTION_RUN", "1.0"),
        ("PROVENANCE_RUN", "1.0"),
    ]
    for activity_type, tool_version in stage_activities:
        graph.add_activity(
            finish_activity(start_activity(activity_type, tool_version), "SUCCEEDED")
        )

    logger.info("lineage built", extra={"nodes": len(graph.nodes), "edges": len(graph.edges)})
    return BuiltProvenance(graph.nodes, graph.edges, graph.activities, graph.artifacts)


def _snapshot_node(snapshot: Any, node_type: Any) -> ProvenanceNode:
    data = snapshot.model_dump(mode="json")
    snapshot_id = (
        data.get("model_snapshot_id")
        or data.get("source_snapshot_id")
        or data.get("environment_snapshot_id")
        or ""
    )
    return ProvenanceNode(
        node_id=snapshot_id,
        node_type=node_type,
        schema_version=snapshot.schema_version,
        payload=data,
    )


def _snapshot_id(snapshot: Any) -> str:
    data = snapshot.model_dump(mode="json")
    found: str = (
        data.get("model_snapshot_id")
        or data.get("source_snapshot_id")
        or data.get("environment_snapshot_id")
        or ""
    )
    return found


def _config_node(name: str, content: Any, schema_version: str) -> ProvenanceNode:
    from .activities import snapshot_config

    snapshot = snapshot_config(name, content, schema_version)
    return ProvenanceNode(
        node_id=snapshot.configuration_id,
        node_type="CONFIGURATION",
        schema_version=snapshot.schema_version,
        payload=snapshot.model_dump(mode="json"),
    )


def _candidate_artifacts(record: Any, candidate_id: str) -> list[Any]:
    raw = record.candidate.raw_response.encode("utf-8")
    sql = (record.candidate.candidate_sql or "").encode("utf-8")
    return [
        artifact_from_bytes(
            raw, "raw_response", f"{candidate_id}.raw.txt", f"artifacts/{candidate_id}.raw.txt"
        ),
        artifact_from_bytes(
            sql, "candidate_sql", f"{candidate_id}.sql", f"artifacts/{candidate_id}.sql"
        ),
    ]


def _artifact_node(artifact: ArtifactRef) -> ProvenanceNode:
    """Content-only ARTIFACT node (placement lives on ArtifactRef records).

    Two references to identical content share one node id; the distinct
    logical locators remain on the individual ArtifactRef records.
    """
    return ProvenanceNode(
        node_id=artifact.artifact_id,
        node_type="ARTIFACT",
        schema_version=artifact.schema_version,
        payload={
            "artifact_id": artifact.artifact_id,
            "artifact_type": artifact.artifact_type,
            "content_hash": artifact.content_hash,
            "size_bytes": artifact.size_bytes,
            "media_type": artifact.media_type,
        },
    )


_TRACE_RANK: dict[str, int] = {
    "TASK_TEMPLATE": 0,
    "TASK_INSTANCE": 1,
    "GENERATION_RUN": 2,
    "MODEL_SNAPSHOT": 3,
    "CONFIGURATION": 3,
    "CANDIDATE_SOLUTION": 4,
    "ARTIFACT": 4,
    "EXECUTION_RUN": 5,
    "EXECUTION_RESULT": 6,
    "VERIFICATION_RUN": 7,
    "VERIFICATION_RESULT": 8,
    "QUALITY_RUN": 9,
    "RECORD_QUALITY": 10,
    "AUDIT_SAMPLE": 11,
    "AUDIT_RESULT": 12,
    "GOLDEN_SELECTION": 13,
    "GOLDEN_RECORD": 14,
    "DATASET_SNAPSHOT": 15,
    "SOURCE_SNAPSHOT": 16,
    "ENVIRONMENT_SNAPSHOT": 16,
}


def roles_for_candidate(
    nodes: dict[str, ProvenanceNode],
    candidate_id: str,
    edges: list[ProvenanceEdge] | None = None,
) -> dict[str, ProvenanceNode]:
    """Resolve one candidate's chain roles (task via candidate's task_id).

    Shared nodes (selection, snapshot) resolve through edges when provided;
    otherwise only payload-linked nodes are returned.
    """
    roles: dict[str, ProvenanceNode] = {}
    for node in nodes.values():
        if node.payload.get("candidate_id") == candidate_id:
            roles[node.node_type] = node
    candidate = roles.get("CANDIDATE_SOLUTION")
    if candidate is not None:
        task_id = candidate.payload.get("task_id")
        for node in nodes.values():
            if node.node_type == "TASK_INSTANCE" and node.payload.get("task_id") == task_id:
                roles["TASK_INSTANCE"] = node
                break
    if edges is not None:
        targets: dict[str, list[str]] = {}
        for edge in edges:
            targets.setdefault(edge.source_id, []).append(edge.target_id)
        quality = roles.get("RECORD_QUALITY")
        if quality is not None:
            for target in targets.get(quality.node_id, []):
                if target in nodes and nodes[target].node_type == "GOLDEN_SELECTION":
                    roles["GOLDEN_SELECTION"] = nodes[target]
        for node_id in list(roles):
            for target in targets.get(node_id, []):
                if target in nodes and nodes[target].node_type == "DATASET_SNAPSHOT":
                    roles["DATASET_SNAPSHOT"] = nodes[target]
    return roles


def trace_golden_record(
    nodes: dict[str, ProvenanceNode], edges: list[ProvenanceEdge], golden_node_id: str
) -> list[str]:
    """Record-scoped chain for one Golden record, oldest first.

    Shared context (selection, configs, models) is fan-out by nature, so a
    naive ancestor walk would absorb every record. Instead the trace
    collects exactly this record's nodes — per-record payloads, the linked
    task/template, the selection reached through edges, and one-hop
    USES_* context — then orders them by canonical chain rank.
    """
    golden = nodes.get(golden_node_id)
    if golden is None or golden.node_type != "GOLDEN_RECORD":
        raise KeyError(f"unknown golden record node: {golden_node_id}")
    candidate_id = golden.payload.get("candidate_id", "")

    selected: set[str] = set()
    for node_id, node in nodes.items():
        if node.payload.get("candidate_id") == candidate_id:
            selected.add(node_id)
    # The task carries task_id (not candidate_id): resolve via the candidate.
    candidate_nodes = [
        n for n in nodes.values() if n.node_id in selected and n.node_type == "CANDIDATE_SOLUTION"
    ]
    task_ids = {n.payload.get("task_id") for n in candidate_nodes}
    for node_id, node in nodes.items():
        if node.node_type == "TASK_INSTANCE" and node.payload.get("task_id") in task_ids:
            selected.add(node_id)
    # Template via the task's DERIVED_FROM edge; selection via quality edge.
    targets: dict[str, list[str]] = {}
    for edge in edges:
        targets.setdefault(edge.source_id, []).append(edge.target_id)
    for node_id in list(selected):
        node = nodes[node_id]
        if node.node_type == "TASK_INSTANCE":
            for target in targets.get(node_id, []):
                if nodes[target].node_type == "TASK_TEMPLATE":
                    selected.add(target)
        if node.node_type == "RECORD_QUALITY":
            for target in targets.get(node_id, []):
                if nodes[target].node_type == "GOLDEN_SELECTION":
                    selected.add(target)
        if node.node_type in ("GENERATION_RUN", "EXECUTION_RUN", "CANDIDATE_SOLUTION"):
            for target in targets.get(node_id, []):
                if nodes[target].node_type in ("MODEL_SNAPSHOT", "CONFIGURATION", "ARTIFACT"):
                    selected.add(target)
    # The golden node itself plus its artifact links.
    selected.add(golden_node_id)
    for target in targets.get(golden_node_id, []):
        if nodes[target].node_type == "ARTIFACT":
            selected.add(target)
    return sorted(selected, key=lambda i: (_TRACE_RANK.get(nodes[i].node_type, 99), i))
