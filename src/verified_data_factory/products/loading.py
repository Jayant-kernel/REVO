"""Release loading for consumers (§29–§31).

``load_release`` is the single supported entry point for reading a
release: it loads the manifest, reads every shard in manifest order,
and re-validates schema + checksums + visibility. Anything malformed
raises ``ProductValidationError`` — consumers never see partial data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import ProductIOError, ProductValidationError
from .manifest import read_manifest
from .models import ProductSchema, ReleaseManifest
from .schemas import canonical_schema, validate_product_record
from .serializers import hash_file, read_jsonl, read_parquet
from .validation import validate_release


class LoadedRelease:
    """A validated release: manifest + ordered records (plain holder)."""

    def __init__(self, manifest: ReleaseManifest, records: list[dict[str, Any]]) -> None:
        self.manifest = manifest
        self.records = records

    def __len__(self) -> int:
        return len(self.records)


def load_release(
    release_dir: str | Path, *, validate: bool = True, schema: ProductSchema | None = None
) -> LoadedRelease:
    """Load and strictly validate a release directory."""
    root = Path(release_dir)
    if not root.is_dir():
        raise ProductIOError(f"release directory not found: {root}")
    manifest = read_manifest(root / "manifest.json")
    active_schema = schema or canonical_schema()

    records: list[dict[str, Any]] = []
    require_sql = manifest.product_type in ("TRAIN", "PRIVATE_EVAL", "BENCHMARK", "SAMPLE")
    for shard in manifest.shards:
        shard_path = root / shard.relative_path
        if not shard_path.exists():
            raise ProductValidationError(f"missing shard: {shard.relative_path}")
        size, digest = hash_file(shard_path)
        if digest != shard.content_hash or size != shard.byte_size:
            raise ProductValidationError(f"shard checksum mismatch: {shard.relative_path}")
        shard_records = (
            read_parquet(shard_path) if shard_path.suffix == ".parquet" else read_jsonl(shard_path)
        )
        for record in shard_records:
            record_errors = validate_product_record(record, active_schema, require_sql=require_sql)
            if record_errors:
                raise ProductValidationError(
                    f"invalid record in {shard.relative_path}: {record_errors[0]}"
                )
        records.extend(shard_records)

    if validate:
        report = validate_release(root)
        if report.status != "VALID":
            first = report.errors[0].detail if report.errors else "unknown validation failure"
            raise ProductValidationError(f"release {root} failed validation: {first}")
    return LoadedRelease(manifest=manifest, records=records)


def records_by_split(loaded: LoadedRelease) -> dict[str, list[dict[str, Any]]]:
    """Group loaded records by their ``split`` marker (train has none)."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in loaded.records:
        key = str(record.get("split", "train"))
        grouped.setdefault(key, []).append(record)
    return grouped
