"""Deterministic serializers: JSONL (canonical) + Parquet (typed) (§19–§21, §39).

JSONL is the canonical interchange format: one UTF-8 line per record,
stable key order, ``\\n`` terminators. Parquet mirrors the JSONL payload
column-for-column (same logical records, same schema version).
Sharding splits a record stream into fixed-size pieces with stable
``shard-{index:05d}`` names; record order is always candidate-id order
unless a split file already fixed it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .errors import ProductIOError

JSONL_MEDIA_TYPE = "application/x-ndjson"
PARQUET_MEDIA_TYPE = "application/vnd.apache.parquet"


def encode_record_line(record: dict[str, Any]) -> bytes:
    """Canonical JSONL encoding for one record (stable keys, UTF-8)."""
    return (
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def decode_record_line(line: bytes, *, lineno: int = 0) -> dict[str, Any]:
    """Strict JSONL decode; malformed lines fail (never repaired)."""
    try:
        value = json.loads(line.decode("utf-8"))
    except Exception as exc:
        raise ProductIOError(f"line {lineno}: invalid JSONL: {exc}") from exc
    if not isinstance(value, dict):
        raise ProductIOError(f"line {lineno}: JSONL record must be an object")
    return value


def write_jsonl(records: list[dict[str, Any]], path: str | Path) -> tuple[int, str]:
    """Write records in given order; returns (byte_size, sha256)."""
    path = Path(path)
    digest = hashlib.sha256()
    size = 0
    with open(path, "wb") as fh:
        for record in records:
            line = encode_record_line(record)
            fh.write(line)
            digest.update(line)
            size += len(line)
    return size, digest.hexdigest()


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Read a JSONL shard strictly (blank lines skipped, order preserved)."""
    records: list[dict[str, Any]] = []
    with open(path, "rb") as fh:
        for lineno, raw in enumerate(fh, 1):
            if not raw.strip():
                continue
            records.append(decode_record_line(raw, lineno=lineno))
    return records


def hash_file(path: str | Path) -> tuple[int, str]:
    """Streaming SHA-256 of a file; returns (byte_size, hex)."""
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def column_names(records: list[dict[str, Any]]) -> list[str]:
    """Stable union of record keys (sorted) for Parquet column order."""
    names: set[str] = set()
    for record in records:
        names.update(record.keys())
    return sorted(names)


def _parquet_arrays(records: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    """Typed Arrow columns preserving JSON scalar types (nulls kept)."""
    import pyarrow as pa  # type: ignore[import-untyped]

    arrays: dict[str, Any] = {}
    for name in columns:
        values = [r.get(name) for r in records]
        non_null = [v for v in values if v is not None]
        if non_null and all(isinstance(v, bool) for v in non_null):
            arrays[name] = pa.array(
                [None if v is None else bool(v) for v in values], type=pa.bool_()
            )
        elif non_null and all(isinstance(v, int) and not isinstance(v, bool) for v in non_null):
            arrays[name] = pa.array(values, type=pa.int64())
        elif non_null and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in non_null
        ):
            arrays[name] = pa.array(
                [None if v is None else float(v) for v in values], type=pa.float64()
            )
        else:
            arrays[name] = pa.array(
                [None if v is None else str(v) for v in values], type=pa.string()
            )
    return arrays


def write_parquet(records: list[dict[str, Any]], path: str | Path) -> tuple[int, str]:
    """Write records as Parquet (JSON scalar types preserved, nulls kept)."""
    import pyarrow as pa
    import pyarrow.parquet as pq  # type: ignore[import-untyped]

    columns = column_names(records)
    table = pa.table(_parquet_arrays(records, columns))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path, version="2.6", use_dictionary=True)
    return hash_file(path)


def read_parquet(path: str | Path) -> list[dict[str, Any]]:
    """Read a Parquet shard back into record dicts (typed columns)."""
    import pyarrow.parquet as pq

    table = pq.read_table(path)
    columns = table.schema.names
    rows = table.to_pylist()
    return [{name: row.get(name) for name in columns} for row in rows]


def shard_records(records: list[dict[str, Any]], shard_size: int) -> list[list[dict[str, Any]]]:
    """Split an ordered record list into fixed-size shards (0/negative = one shard)."""
    if shard_size <= 0:
        return [list(records)]
    return [records[i : i + shard_size] for i in range(0, len(records), shard_size)]


def shard_filename(index: int, output_format: str) -> str:
    suffix = {"jsonl": "jsonl", "parquet": "parquet"}.get(output_format, output_format)
    return f"shard-{index:05d}.{suffix}"
