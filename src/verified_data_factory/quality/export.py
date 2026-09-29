"""Golden dataset export (Phase 5).

Deterministic internal export (sorted by candidate_id, no timestamps):
golden/excluded/inconclusive JSONL, dataset health JSON, audit sample
JSONL. Golden records follow docs/golden-record.md. Volatile telemetry
(verification timestamps, oracle runtime, performance duration) is
projected out of exported blobs so repeated runs are byte-identical;
semantic evidence is untouched. No commercial packaging, licensing, or
marketplace logic — that is Phase 7+.
"""

from __future__ import annotations

import json
import hashlib
import logging
from pathlib import Path
from typing import Any

from .models import GoldenRecord, RecordQuality, VerifiedRecord

_VOLATILE_VERIFICATION_PATHS = (
    ("started_at",),
    ("finished_at",),
    ("oracle", "runtime_ms"),
    ("performance", "duration_ms"),
)


def stable_verification_blob(verification: Any) -> dict[str, Any]:
    """Verification evidence minus run-varying telemetry (deterministic)."""
    blob: dict[str, Any] = verification.model_dump(mode="json")
    for path in _VOLATILE_VERIFICATION_PATHS:
        node: Any = blob
        for key in path[:-1]:
            if not isinstance(node, dict):
                node = None
                break
            node = node.get(key)
        if isinstance(node, dict):
            node.pop(path[-1], None)
    return blob


logger = logging.getLogger(__name__)


def build_golden_record_id(
    *,
    task: dict[str, Any],
    instruction: str,
    schema: list[dict[str, Any]],
    candidate_solution: str,
    record_schema_version: str = "2.0",
) -> str:
    """Bind one Golden identity to its immutable semantic content."""
    payload = {
        "record_schema_version": record_schema_version,
        "task": task,
        "instruction": instruction,
        "schema": schema,
        "candidate_solution": candidate_solution,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}"


def golden_record_for(quality: RecordQuality, record: VerifiedRecord) -> GoldenRecord:
    """Assemble one canonical Golden record from its inputs + quality."""
    task = record.task.model_dump(mode="json", by_alias=True)
    schema = [t.model_dump(mode="json") for t in record.task.schema_]
    solution = record.candidate.candidate_sql or ""
    return GoldenRecord(
        record_id=build_golden_record_id(
            task=task,
            instruction=record.task.instruction,
            schema=schema,
            candidate_solution=solution,
        ),
        candidate_id=quality.candidate_id,
        task=task,
        instruction=record.task.instruction,
        schema_=schema,
        fixture={
            "seed": record.task.seed,
            "engine": record.task.fixture_metadata.engine,
            "generation_version": record.task.fixture_metadata.generation_version,
            "tables": {
                name: meta.row_count for name, meta in record.task.fixture_metadata.tables.items()
            },
            "edge_cases": list(record.task.edge_cases),
        },
        candidate_solution=solution,
        verification=stable_verification_blob(record.verification),
        quality=quality.model_dump(mode="json"),
        dataset_role=record.role,
        audit_status=quality.auditor_result,
    )


def export_dataset(
    qualities: list[RecordQuality],
    records: dict[str, VerifiedRecord],
    health: dict[str, Any],
    audit_items: list[dict[str, Any]],
    out_dir: str | Path,
) -> dict[str, str]:
    """Write golden/excluded/inconclusive/health/audit artifacts. Returns paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    by_decision: dict[str, list[RecordQuality]] = {
        "GOLDEN": [],
        "EXCLUDED": [],
        "INCONCLUSIVE": [],
        "AUDIT_REQUIRED": [],
    }
    for quality in sorted(qualities, key=lambda q: q.candidate_id):
        by_decision[quality.decision].append(quality)

    paths: dict[str, str] = {}
    names = {
        "GOLDEN": "golden.jsonl",
        "EXCLUDED": "excluded.jsonl",
        "INCONCLUSIVE": "inconclusive.jsonl",
        "AUDIT_REQUIRED": "audit_required.jsonl",
    }
    for decision, filename in names.items():
        path = out / filename
        with path.open("w", encoding="utf-8") as fh:
            for quality in by_decision[decision]:
                record = records[quality.candidate_id]
                if decision == "GOLDEN":
                    blob = golden_record_for(quality, record).model_dump(mode="json", by_alias=True)
                else:
                    blob = {
                        "candidate_id": quality.candidate_id,
                        "task_id": quality.task_id,
                        "decision": quality.decision,
                        "reasons": list(quality.decision_reasons),
                    }
                fh.write(json.dumps(blob, sort_keys=True) + "\n")
        paths[decision.lower()] = str(path)

    health_path = out / "dataset_health.json"
    health_path.write_text(json.dumps(health, sort_keys=True, indent=2), encoding="utf-8")
    paths["health"] = str(health_path)

    audit_path = out / "audit_sample.jsonl"
    with audit_path.open("w", encoding="utf-8") as fh:
        for item in sorted(audit_items, key=lambda i: i["audit_id"]):
            fh.write(json.dumps(item, sort_keys=True) + "\n")
    paths["audit"] = str(audit_path)

    logger.info(
        "dataset export complete",
        extra={
            "dir": str(out),
            **{k: len(by_decision[d]) for k, d in (("golden", "GOLDEN"), ("excluded", "EXCLUDED"))},
        },
    )
    return paths
