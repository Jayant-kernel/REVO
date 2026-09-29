"""Serializer round-trip and determinism tests (Phase 7, §19–§21)."""

import pytest

from verified_data_factory.products import (
    decode_record_line,
    encode_record_line,
    hash_file,
    read_jsonl,
    read_parquet,
    shard_filename,
    shard_records,
    write_jsonl,
    write_parquet,
)
from verified_data_factory.products.errors import ProductIOError

RECORDS = [
    {"golden_record_id": "c-002", "sql": "SELECT 2;", "difficulty": 2},
    {"golden_record_id": "c-001", "sql": "SELECT 1;", "difficulty": 1},
]


def test_jsonl_line_encoding_is_canonical(tmp_path):
    # Key order in memory must not affect bytes on disk.
    line_a = encode_record_line({"b": 1, "a": 2})
    line_b = encode_record_line({"a": 2, "b": 1})
    assert line_a == line_b
    assert line_a.endswith(b"\n")
    assert decode_record_line(line_a) == {"a": 2, "b": 1}


def test_jsonl_roundtrip_preserves_order(tmp_path):
    path = tmp_path / "data.jsonl"
    size, digest = write_jsonl(RECORDS, path)
    assert size > 0 and len(digest) == 64
    assert read_jsonl(path) == RECORDS


def test_jsonl_malformed_line_fails(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_bytes(b'{"ok": true}\nnot json\n')
    with pytest.raises(ProductIOError):
        read_jsonl(path)


def test_jsonl_non_object_line_fails(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_bytes(b"[1, 2]\n")
    with pytest.raises(ProductIOError):
        read_jsonl(path)


def test_parquet_roundtrip(tmp_path):
    path = tmp_path / "data.parquet"
    size, digest = write_parquet(RECORDS, path)
    assert size > 0 and len(digest) == 64
    rows = read_parquet(path)
    assert [r["golden_record_id"] for r in rows] == ["c-002", "c-001"]


def test_parquet_empty_frame_roundtrip(tmp_path):
    path = tmp_path / "empty.parquet"
    write_parquet([], path)
    assert read_parquet(path) == []


def test_sharding_sizes_and_names():
    records = [{"golden_record_id": f"c-{i:03d}"} for i in range(7)]
    shards = shard_records(records, 3)
    assert [len(s) for s in shards] == [3, 3, 1]
    assert shard_filename(0, "jsonl") == "shard-00000.jsonl"
    assert shard_filename(12, "parquet") == "shard-00012.parquet"
    assert len(shard_records(records, 0)) == 1


def test_hash_file_stable(tmp_path):
    path = tmp_path / "data.jsonl"
    write_jsonl(RECORDS, path)
    assert hash_file(path) == hash_file(path)
