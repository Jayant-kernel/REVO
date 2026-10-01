"""Release building and diffing (§22–§28, §35–§37).

``build_release`` is the single supported path from a Golden snapshot to
a validated release directory: visibility filtering → deterministic
splitting → profiled transformation → sharded serialization → manifest +
checksums + card + preview → self-validation. The source snapshot is
never modified; rebuilding identical inputs yields an identical
``release_id`` (timestamps excluded from identity).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from verified_data_factory.provenance.models import DatasetSnapshot
from verified_data_factory.quality.models import GoldenRecord

from .errors import ProductConfigError, ProductIOError
from .manifest import (
    build_manifest,
    read_manifest,
    render_dataset_card,
    write_checksums,
    write_manifest,
    write_preview,
)
from .metrics import build_metrics, metrics_payload
from .models import (
    PRODUCT_SCHEMA_VERSION,
    BenchmarkRecord,
    EvaluationRecord,
    ProductConfig,
    ProductType,
    ReleaseDiff,
    ReleaseFile,
    ReleaseManifest,
    ReleaseValidationReport,
    ShardManifest,
    SplitName,
    TrainingRecord,
)
from .profiles import profile_for_type
from .schemas import canonical_schema
from .selection import select_visible_records
from .serializers import (
    JSONL_MEDIA_TYPE,
    PARQUET_MEDIA_TYPE,
    hash_file,
    read_jsonl,
    read_parquet,
    shard_filename,
    shard_records,
    write_jsonl,
    write_parquet,
)
from .splits import build_splits
from .transforms import to_benchmark_record, to_evaluation_record, to_training_record
from .validation import validate_release

SAMPLE_RECORD_LIMIT = 25


class BuiltRelease:
    """Outcome of one release build (plain holder)."""

    def __init__(
        self,
        manifest: ReleaseManifest,
        validation: ReleaseValidationReport,
        rejected: list[tuple[str, list[str]]],
        release_dir: Path,
    ) -> None:
        self.manifest = manifest
        self.validation = validation
        self.rejected = rejected
        self.release_dir = release_dir


def _snapshot_member(golden: GoldenRecord, member_set: set[str]) -> bool:
    """True when a Golden record belongs to a snapshot's membership set."""
    if golden.candidate_id in member_set:
        return True
    if golden.record_id in member_set:
        return True
    from verified_data_factory.provenance.nodes import golden_record_node

    try:
        return golden_record_node(golden).payload.get("golden_content_hash") in member_set
    except Exception:  # noqa: BLE001 — unhashable records simply do not match
        return False


def _product_split(config: ProductConfig) -> SplitName:
    mapping: dict[ProductType, SplitName] = {
        "TRAIN": "train",
        "PUBLIC_EVAL": "public_eval",
        "PRIVATE_EVAL": "private_eval",
        "BENCHMARK": "benchmark",
        "SAMPLE": "train",
    }
    return mapping[config.product_type]


def build_release(
    *,
    snapshot: DatasetSnapshot,
    golden_records: list[GoldenRecord],
    quality_by_id: dict[str, dict[str, Any]],
    config: ProductConfig,
    out_dir: str | Path,
    factory_version: str,
    provenance_version: str,
    health: dict[str, Any] | None = None,
    coverage: dict[str, Any] | None = None,
    duplicates: dict[str, Any] | None = None,
    verification_summary: dict[str, Any] | None = None,
    audit_summary: dict[str, Any] | None = None,
    contamination: dict[str, Any] | None = None,
    quarantined_ids: set[str] | None = None,
    justifications: dict[str, str] | None = None,
    supply_chain: dict[str, Any] | None = None,
    review_package: str | Path | None = None,
) -> BuiltRelease:
    """Build, persist, and self-validate one product release.

    ``quarantined_ids`` refuses the build when a snapshot member is
    quarantined — quarantined records can never ship.
    """
    profile = profile_for_type(config.product_type)
    schema = canonical_schema()
    out = Path(out_dir)

    # Snapshot members are content ids by Phase 6 design ("record content,
    # not candidate ids alone"); older snapshots may carry candidate ids.
    # Accept either, so CLI-built bundles resolve.
    member_set = set(snapshot.golden_record_ids)
    in_snapshot = [g for g in golden_records if _snapshot_member(g, member_set)]
    if len(in_snapshot) != len(
        {g.candidate_id for g in golden_records if _snapshot_member(g, member_set)}
    ):
        raise ProductConfigError("duplicate golden records supplied for one snapshot")
    if not in_snapshot:
        raise ProductConfigError("no supplied golden records are members of the dataset snapshot")
    quarantine_evidence = quarantined_ids
    quarantined_ids = quarantined_ids or set()
    quarantined_members = sorted({g.candidate_id for g in in_snapshot} & quarantined_ids)
    if quarantined_members:
        raise ProductConfigError(
            f"quarantined records in snapshot scope refuse the build: {quarantined_members}"
        )

    allowed, rejected = select_visible_records(in_snapshot, quality_by_id, config.visibility)
    splits = build_splits(allowed, quality_by_id, config.split_policy)
    by_id = {g.candidate_id: g for g in allowed}

    wanted = _product_split(config)
    if config.product_type == "BENCHMARK":
        source_ids = list(splits["public_eval"].candidate_ids)
    else:
        source_ids = list(splits[wanted].candidate_ids)
    if config.product_type == "SAMPLE":
        source_ids = source_ids[:SAMPLE_RECORD_LIMIT]

    product_records: list[dict[str, Any]] = []
    for position, candidate_id in enumerate(source_ids):
        golden = by_id[candidate_id]
        record: TrainingRecord | EvaluationRecord | BenchmarkRecord
        if config.product_type in ("TRAIN", "SAMPLE"):
            record = to_training_record(golden, snapshot.dataset_snapshot_id)
        elif config.product_type == "BENCHMARK":
            record = to_benchmark_record(
                golden, snapshot.dataset_snapshot_id, "benchmark", profile, position
            )
        else:
            split_name: SplitName = "public_eval" if wanted == "public_eval" else "private_eval"
            record = to_evaluation_record(golden, snapshot.dataset_snapshot_id, split_name, profile)
        payload = record.model_dump(by_alias=True, mode="json")
        if not profile.include_sql_target:
            # Target exposure is a profile decision; the transform already
            # omits it, this drop is defense-in-depth before serialization.
            payload.pop("sql", None)
        product_records.append(payload)

    product_records.sort(key=lambda r: str(r.get("golden_record_id", "")))

    data_dir = out / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    shards: list[ShardManifest] = []
    for index, shard in enumerate(shard_records(product_records, config.shard_size)):
        filename = shard_filename(index, config.output_format)
        shard_path = data_dir / filename
        relative = f"data/{filename}"
        if config.output_format == "parquet":
            size, digest = write_parquet(shard, shard_path)
        else:
            size, digest = write_jsonl(shard, shard_path)
        shards.append(
            ShardManifest(
                shard_id=f"shard-{index:05d}",
                relative_path=relative,
                record_count=len(shard),
                byte_size=size,
                content_hash=digest,
            )
        )
    if not shards:
        # Empty product still ships a valid (empty) shard so consumers
        # always see a uniform layout.
        filename = shard_filename(0, config.output_format)
        shard_path = data_dir / filename
        relative = f"data/{filename}"
        if config.output_format == "parquet":
            size, digest = write_parquet([], shard_path)
        else:
            size, digest = write_jsonl([], shard_path)
        shards.append(
            ShardManifest(
                shard_id="shard-00000",
                relative_path=relative,
                record_count=0,
                byte_size=size,
                content_hash=digest,
            )
        )

    split_counts: dict[str, int] = {str(name): split.record_count for name, split in splits.items()}
    media_type = PARQUET_MEDIA_TYPE if config.output_format == "parquet" else JSONL_MEDIA_TYPE
    manifest = build_manifest(
        config=config,
        schema=schema,
        policy=config.split_policy,
        dataset_snapshot_id=snapshot.dataset_snapshot_id,
        split_counts=split_counts,
        shards=shards,
        files=[
            ReleaseFile(
                relative_path=s.relative_path,
                byte_size=s.byte_size,
                content_hash=s.content_hash,
                media_type=media_type,
            )
            for s in shards
        ],
        factory_version=factory_version,
        provenance_version=provenance_version,
    )
    # ``split_counts`` is the full deterministic plan (all four splits);
    # ``record_count`` is what this release actually ships (one product split).
    # Shard hashes already fix the shipped content, so the release id is
    # unaffected by this derived count.
    manifest = manifest.model_copy(update={"record_count": len(product_records)})

    write_manifest(manifest, out / "manifest.json")
    write_checksums(
        {s.relative_path: (s.byte_size, s.content_hash) for s in shards}
        | {"manifest.json": hash_file(out / "manifest.json")},
        out / "SHA256SUMS",
    )
    metrics = build_metrics(
        split_counts=split_counts,
        product_records=product_records,
        health=health,
        coverage=coverage,
        duplicates=duplicates,
        verification_summary=verification_summary,
        audit_summary=audit_summary,
        contamination=contamination,
    )
    (out / "metrics.json").write_text(
        json.dumps(metrics_payload(metrics), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    card_warnings = [f"excluded {len(rejected)} record(s) by visibility policy"] if rejected else []
    (out / "dataset_card.md").write_text(
        render_dataset_card(
            manifest=manifest,
            schema=schema,
            metrics=metrics_payload(metrics),
            warnings=card_warnings,
        ),
        encoding="utf-8",
    )
    write_preview(product_records, out / "preview.json", config.preview_size)

    shipped_quality = {
        golden.record_id: quality_by_id[golden.candidate_id]
        for golden in allowed
        if golden.candidate_id in quality_by_id
    }
    report = validate_release(
        out,
        quarantined_ids=quarantine_evidence,
        qualities_by_id=shipped_quality,
        justifications=justifications,
        supply_chain=supply_chain,
        review_package=review_package,
    )
    if report.status != "VALID":
        first = report.errors[0].detail if report.errors else "unknown failure"
        raise ProductIOError(f"built release failed self-validation: {first}")
    return BuiltRelease(manifest=manifest, validation=report, rejected=rejected, release_dir=out)


def _release_record_hashes(release_dir: Path, manifest: ReleaseManifest) -> dict[str, str]:
    """Map golden_record_id → canonical content hash for one release."""
    from verified_data_factory.provenance import canonical_bytes

    hashes: dict[str, str] = {}
    for shard in manifest.shards:
        shard_path = release_dir / shard.relative_path
        shard_records = (
            read_parquet(shard_path) if shard_path.suffix == ".parquet" else read_jsonl(shard_path)
        )
        for record in shard_records:
            gid = str(record.get("golden_record_id", ""))
            if gid:
                hashes[gid] = canonical_bytes(record).decode("utf-8")
    return hashes


def diff_releases(dir_a: str | Path, dir_b: str | Path) -> ReleaseDiff:
    """Compare two release directories (records, splits, schema, config)."""
    root_a, root_b = Path(dir_a), Path(dir_b)
    manifest_a = read_manifest(root_a / "manifest.json")
    manifest_b = read_manifest(root_b / "manifest.json")
    hashes_a = _release_record_hashes(root_a, manifest_a)
    hashes_b = _release_record_hashes(root_b, manifest_b)
    ids_a, ids_b = set(hashes_a), set(hashes_b)
    return ReleaseDiff(
        release_a=manifest_a.release_id,
        release_b=manifest_b.release_id,
        records_added=sorted(ids_b - ids_a),
        records_removed=sorted(ids_a - ids_b),
        records_changed=sorted(i for i in ids_a & ids_b if hashes_a[i] != hashes_b[i]),
        splits_changed=manifest_a.split_counts != manifest_b.split_counts,
        schema_changed=(manifest_a.schema_name, manifest_a.schema_version)
        != (manifest_b.schema_name, manifest_b.schema_version),
        config_changed=manifest_a.product_config_id != manifest_b.product_config_id,
        snapshot_changed=manifest_a.dataset_snapshot_id != manifest_b.dataset_snapshot_id,
        format_changed=manifest_a.output_format != manifest_b.output_format,
        schema_version=PRODUCT_SCHEMA_VERSION,
    )
