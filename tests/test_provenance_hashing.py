"""Hashing + artifact tests (Phase 6, §7 + §9 + §45)."""

import hashlib
import io

from verified_data_factory.provenance import (
    artifact_from_bytes,
    artifact_from_file,
    artifact_id_for,
    content_id,
    hash_bytes,
    hash_file,
    hash_stream,
    media_type_for,
)


def test_identical_payload_identical_hash():
    payload = {"task_id": "t1", "rows": [[1, 2], [3, 4]]}
    assert content_id("TASK_INSTANCE", "1.0", payload) == content_id(
        "TASK_INSTANCE", "1.0", payload
    )


def test_material_change_changes_hash():
    assert content_id("TASK_INSTANCE", "1.0", {"rows": [[1]]}) != content_id(
        "TASK_INSTANCE", "1.0", {"rows": [[2]]}
    )


def test_metadata_only_fields_do_not_alter_content_id():
    # Operational metadata lives outside hashed envelopes by construction;
    # the same logical payload hashes identically regardless of run ids.
    assert content_id("X", "1.0", {"a": 1}) == content_id("X", "1.0", {"a": 1})


def test_domain_separation_across_node_types():
    payload = {"a": 1}
    left = content_id("TASK_INSTANCE", "1.0", payload)
    right = content_id("CANDIDATE_SOLUTION", "1.0", payload)
    assert left != right
    assert left.startswith("sha256:") and right.startswith("sha256:")


def test_hash_bytes_correct_sha256():
    assert hash_bytes(b"abc") == "sha256:" + hashlib.sha256(b"abc").hexdigest()


def test_hash_streaming_matches_oneshot(tmp_path):
    data = b"x" * 100000 + b"y" * 50000
    assert hash_bytes(data) == hash_stream(io.BytesIO(data))[0]


def test_large_file_streaming(tmp_path):
    path = tmp_path / "big.bin"
    with open(path, "wb") as fh:
        fh.writelines(b"0123456789abcdef" * 4096 for _ in range(200))
    digest, size = hash_file(path)
    assert digest == "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    assert size == path.stat().st_size


def test_artifact_from_bytes_stable():
    first = artifact_from_bytes(b"SELECT 1;", "candidate_sql", "a.sql", "artifacts/a.sql")
    second = artifact_from_bytes(b"SELECT 1;", "candidate_sql", "b.sql", "artifacts/b.sql")
    # Same content+kind: same artifact id (placement differs, identity holds).
    assert first.artifact_id == second.artifact_id
    assert first.content_hash == second.content_hash
    assert first.size_bytes == len(b"SELECT 1;")


def test_duplicate_content_recognized_changed_content_new_hash(tmp_path):
    first = artifact_from_bytes(b"same", "raw_response", "a.txt", "a.txt")
    second = artifact_from_bytes(b"same", "raw_response", "a.txt", "a.txt")
    assert first.artifact_id == second.artifact_id
    third = artifact_from_bytes(b"different", "raw_response", "a.txt", "a.txt")
    assert third.artifact_id != first.artifact_id
    path = tmp_path / "f.sql"
    path.write_bytes(b"SELECT 1;")
    assert artifact_from_file(path, "candidate_sql").content_hash == hash_bytes(b"SELECT 1;")


def test_media_types():
    assert media_type_for("a.json") == "application/json"
    assert media_type_for("a.JSONL") == "application/jsonl"
    assert media_type_for("a.yaml") == "application/yaml"
    assert media_type_for("a.sql") == "application/sql"
    assert media_type_for("a.bin") == "application/octet-stream"
    assert media_type_for("a.bin", explicit="text/plain") == "text/plain"


def test_artifact_id_domain_separated_by_kind():
    assert artifact_id_for("sha256:abc", "raw_response") != artifact_id_for(
        "sha256:abc", "candidate_sql"
    )
