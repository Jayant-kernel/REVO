"""Release identity, manifests, checksums, cards, previews (§22–§26, §42).

``release_id`` is content-defined: it covers the canonical manifest
payload only — timestamps and run ids never enter it, so rebuilding the
same inputs yields the same release. SHA256SUMS is written streaming
(no whole-release buffering) and covers every shipped file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from verified_data_factory.provenance import canonical_bytes, content_id, utc_now_iso

from .config import product_config_id, split_policy_id
from .models import (
    PRODUCT_SCHEMA_VERSION,
    ProductConfig,
    ProductSchema,
    ReleaseFile,
    ReleaseManifest,
    ShardManifest,
    SplitName,
    SplitPolicy,
)

RELEASE_ID_NAMESPACE = "DATA_PRODUCT_RELEASE"


def release_id_for(
    *,
    dataset_snapshot_id: str,
    product_config_id: str,
    split_policy_id: str,
    schema_name: str,
    schema_version: str,
    transformation_version: str,
    output_format: str,
    split_counts: dict[str, int],
    shard_hashes: list[str],
) -> str:
    """Content-defined release identity (no timestamps, no paths)."""
    payload = {
        "dataset_snapshot_id": dataset_snapshot_id,
        "output_format": output_format,
        "schema_name": schema_name,
        "schema_version": schema_version,
        "shard_hashes": sorted(shard_hashes),
        "split_counts": {k: split_counts[k] for k in sorted(split_counts)},
        "split_policy_id": split_policy_id,
        "transformation_version": transformation_version,
        "product_config_id": product_config_id,
    }
    return content_id(RELEASE_ID_NAMESPACE, PRODUCT_SCHEMA_VERSION, payload)


def build_manifest(
    *,
    config: ProductConfig,
    schema: ProductSchema,
    policy: SplitPolicy,
    dataset_snapshot_id: str,
    split_counts: dict[str, int],
    shards: list[ShardManifest],
    files: list[ReleaseFile],
    factory_version: str,
    provenance_version: str,
) -> ReleaseManifest:
    """Assemble the authoritative release descriptor."""
    config_id = product_config_id(config)
    policy_id = split_policy_id(policy)
    release_id = release_id_for(
        dataset_snapshot_id=dataset_snapshot_id,
        product_config_id=config_id,
        split_policy_id=policy_id,
        schema_name=schema.schema_name,
        schema_version=schema.schema_version,
        transformation_version=schema.transformation_version,
        output_format=config.output_format,
        split_counts=split_counts,
        shard_hashes=[s.content_hash for s in shards],
    )
    return ReleaseManifest(
        product_name=config.product_name,
        product_type=config.product_type,
        visibility=config.visibility,
        release_id=release_id,
        dataset_snapshot_id=dataset_snapshot_id,
        schema_name=schema.schema_name,
        schema_version=schema.schema_version,
        product_config_id=config_id,
        split_policy_id=policy_id,
        transformation_version=schema.transformation_version,
        output_format=config.output_format,
        record_count=sum(split_counts.values()),
        split_counts=dict(split_counts),
        shard_count=len(shards),
        shards=list(shards),
        files=list(files),
        created_at=utc_now_iso(),
        factory_version=factory_version,
        provenance_version=provenance_version,
        manifest_schema_version=PRODUCT_SCHEMA_VERSION,
    )


def write_manifest(manifest: ReleaseManifest, path: str | Path) -> None:
    """Persist the manifest with stable key order (timestamps excluded from identity)."""
    Path(path).write_text(
        canonical_bytes(manifest.model_dump(mode="json")).decode("utf-8") + "\n", encoding="utf-8"
    )


def read_manifest(path: str | Path) -> ReleaseManifest:
    """Strict manifest load (malformed manifests fail, never repaired)."""
    from .errors import ProductValidationError

    try:
        import json

        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return ReleaseManifest.model_validate(payload)
    except Exception as exc:
        raise ProductValidationError(f"invalid manifest {path}: {exc}") from exc


def write_checksums(files: dict[str, tuple[int, str]], path: str | Path) -> None:
    """Write BSD-style ``SHA256 (file) = hex`` lines in sorted path order.

    ``files`` maps relative path → (byte_size, sha256). Streaming hashes
    are computed by callers; this writer only formats.
    """
    lines = [f"SHA256 ({rel}) = {digest}\n" for rel, (_, digest) in sorted(files.items())]
    Path(path).write_text("".join(lines), encoding="utf-8")


def read_checksums(path: str | Path) -> dict[str, str]:
    """Parse a SHA256SUMS file into relative path → hex digest."""
    from .errors import ProductValidationError

    entries: dict[str, str] = {}
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            left, digest = line.rsplit("=", 1)
            name = left.split("(", 1)[1].rsplit(")", 1)[0].strip()
            entries[name.strip()] = digest.strip()
        except Exception as exc:
            raise ProductValidationError(
                f"{path}:{lineno}: malformed checksum line: {exc}"
            ) from exc
    return entries


def render_dataset_card(
    *,
    manifest: ReleaseManifest,
    schema: ProductSchema,
    metrics: dict[str, Any],
    splits: dict[SplitName, Any] | None = None,
    warnings: list[str] | None = None,
) -> str:
    """Render a factual dataset card from actual metrics (no marketing claims)."""
    lines = [
        f"# {manifest.product_name}",
        "",
        f"- product_type: {manifest.product_type}",
        f"- visibility: {manifest.visibility}",
        f"- release_id: {manifest.release_id}",
        f"- dataset_snapshot_id: {manifest.dataset_snapshot_id}",
        f"- schema: {manifest.schema_name} {manifest.schema_version}",
        f"- dialect: {schema.dialect}",
        f"- transformation_version: {manifest.transformation_version}",
        f"- output_format: {manifest.output_format}",
        f"- records: {manifest.record_count} across {manifest.shard_count} shard(s)",
        f"- split_counts: {dict(sorted(manifest.split_counts.items()))}",
        f"- factory_version: {manifest.factory_version}",
        f"- provenance_version: {manifest.provenance_version}",
        "",
        "## Intended use",
        "",
        "- Training and evaluation of analytical-SQL (DuckDB) models.",
        "- Splits are deterministic; group isolation is enforced at build time.",
        "",
        "## Metrics (from Phase 5, referenced not recomputed)",
        "",
    ]
    for key in sorted(metrics):
        lines.append(f"- {key}: {metrics[key]}")
    if warnings:
        lines += ["", "## Caveats", ""]
        lines += [f"- {warning}" for warning in warnings]
    lines += ["", "## Provenance", "", f"- dataset_snapshot_id: {manifest.dataset_snapshot_id}", ""]
    return "\n".join(lines)


def write_preview(records: list[dict[str, Any]], path: str | Path, preview_size: int) -> int:
    """Write the first ``preview_size`` records as pretty JSON (0 = skip)."""
    if preview_size <= 0:
        return 0
    import json

    preview = records[:preview_size]
    Path(path).write_text(
        json.dumps(preview, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return len(preview)
