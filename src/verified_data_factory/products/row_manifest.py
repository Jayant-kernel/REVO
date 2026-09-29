"""Per-row provenance manifests for samples and releases (§5 remediation).

Every exported row carries machine-readable pointers back through the
pipeline (task → candidate → execution → verification → quality →
selection → snapshot → release). Customer views expose only the
allowlisted keys; run ids and internal references stay internal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import ProductValidationError
from .models import PRODUCT_SCHEMA_VERSION, ROW_MANIFEST_PUBLIC_KEYS, RowManifest

__all__ = [
    "ROW_MANIFEST_PUBLIC_KEYS",
    "RowManifest",
    "build_row_manifest",
    "manifest_identity_summary",
    "public_row_view",
    "read_row_manifest",
    "validate_row_manifest",
    "write_row_manifest",
]


def _nested(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    node: Any = record
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return default
        node = node[key]
    return node


def build_row_manifest(
    *,
    golden_records: list[dict[str, Any]],
    quality_by_id: dict[str, dict[str, Any]],
    dataset_snapshot_id: str,
    release_id: str | None = None,
    generation_run_id: str | None = None,
    quality_run_id: str | None = None,
    golden_selection: str | None = None,
    candidates_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[RowManifest]:
    """Assemble one manifest row per Golden record, sorted by record_id.

    Model origin resolves from ``candidates_by_id`` (VerifiedRecord
    candidate payloads) first: Golden exports carry no model fields, so
    rows without candidate evidence keep model "unknown" and fail
    validation rather than inventing provenance.
    """
    candidates_by_id = candidates_by_id or {}
    rows: list[RowManifest] = []
    for golden in sorted(golden_records, key=lambda g: str(g.get("candidate_id", ""))):
        candidate_id = str(golden.get("candidate_id", ""))
        task = golden.get("task", {}) if isinstance(golden.get("task"), dict) else {}
        candidate = dict(candidates_by_id.get(candidate_id, {}))
        for key in ("model", "model_revision", "prompt_version"):
            if key not in candidate:
                nested = golden.get("candidate", {})
                if isinstance(nested, dict) and key in nested:
                    candidate[key] = nested[key]
                elif key in golden:
                    candidate[key] = golden[key]
        verification = (
            golden.get("verification", {}) if isinstance(golden.get("verification"), dict) else {}
        )
        rows.append(
            RowManifest(
                record_id=candidate_id,
                task_id=str(task.get("task_id", golden.get("task_id", candidate_id))),
                family=str(task.get("family", golden.get("family", "unknown"))),
                template_id=str(task.get("template_id", "unknown")),
                template_version=int(task.get("template_version", 1) or 1),
                model_name=str(candidate.get("model", golden.get("model", "unknown"))),
                model_revision=str(
                    candidate.get("model_revision", golden.get("model_revision", "UNKNOWN"))
                ),
                prompt_version=str(
                    candidate.get("prompt_version", golden.get("prompt_version", ""))
                ),
                generation_run_id=generation_run_id,
                candidate_id=candidate_id,
                execution_run_id=verification.get("execution_id"),
                verification_run_id=verification.get("verification_id"),
                quality_run_id=quality_run_id,
                golden_selection=golden_selection
                or (quality_by_id.get(candidate_id, {}).get("decision")),
                dataset_snapshot_id=dataset_snapshot_id,
                release_id=release_id,
                schema_version=PRODUCT_SCHEMA_VERSION,
            )
        )
    return rows


def public_row_view(row: RowManifest) -> dict[str, Any]:
    """Customer-visible subset; internal run ids are dropped, never leaked."""
    return {key: getattr(row, key) for key in ROW_MANIFEST_PUBLIC_KEYS}


def write_row_manifest(rows: list[RowManifest], path: str | Path) -> Path:
    """Deterministic JSONL export sorted by record_id."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda r: r.record_id)
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(
            json.dumps(row.model_dump(mode="json"), sort_keys=True) + "\n" for row in ordered
        )
    return path


def read_row_manifest(path: str | Path) -> list[RowManifest]:
    try:
        with open(path, encoding="utf-8-sig") as fh:
            return [RowManifest.model_validate(json.loads(line)) for line in fh if line.strip()]
    except Exception as exc:
        raise ProductValidationError(f"invalid row manifest {path}: {exc}") from exc


def validate_row_manifest(
    rows: list[RowManifest],
    *,
    require_snapshot: str | None = None,
    allowed_models: set[str] | None = None,
    quarantined_ids: set[str] | None = None,
) -> list[str]:
    """Return violations (empty means every row traces completely)."""
    violations: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row.record_id in seen:
            violations.append(f"duplicate manifest row: {row.record_id}")
        seen.add(row.record_id)
        for field in (
            "task_id",
            "family",
            "template_id",
            "model_name",
            "candidate_id",
            "dataset_snapshot_id",
        ):
            if not getattr(row, field) or getattr(row, field) in ("unknown",):
                violations.append(f"{row.record_id}: missing required provenance: {field}")
        if require_snapshot is not None and row.dataset_snapshot_id != require_snapshot:
            violations.append(
                f"{row.record_id}: snapshot {row.dataset_snapshot_id} != required {require_snapshot}"
            )
        if allowed_models is not None and row.model_name not in allowed_models:
            violations.append(f"{row.record_id}: model {row.model_name} outside allowed set")
        if quarantined_ids and row.record_id in quarantined_ids:
            violations.append(f"{row.record_id}: quarantined record present in manifest")
    models = {row.model_name for row in rows}
    revisions = {row.model_revision for row in rows}
    if len(models) > 1 or len(revisions) > 1:
        violations.append(
            "manifest mixes run identities: "
            f"models={sorted(models)} revisions={sorted(revisions)}; "
            "split by model revision before release"
        )
    return violations


def manifest_identity_summary(rows: list[RowManifest]) -> dict[str, Any]:
    """Distinct run/model/revision sets so mixes are visible, never silent."""
    return {
        "record_count": len(rows),
        "models": sorted({row.model_name for row in rows}),
        "model_revisions": sorted({row.model_revision for row in rows}),
        "prompt_versions": sorted({row.prompt_version for row in rows}),
        "snapshots": sorted({row.dataset_snapshot_id for row in rows}),
        "releases": sorted({row.release_id for row in rows if row.release_id}),
    }
