"""Artifact references (Phase 6, §9 + §34).

Artifacts are referenced and hashed — never duplicated into the store.
Large files stream; content identity is stable across locations.
"""

from __future__ import annotations

from pathlib import Path

from .hashing import content_id, hash_bytes, hash_file
from .models import PROVENANCE_SCHEMA_VERSION, ArtifactRef

_MEDIA_TYPES = {
    ".json": "application/json",
    ".jsonl": "application/jsonl",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".sql": "application/sql",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".parquet": "application/parquet",
    ".db": "application/x-duckdb",
    ".duckdb": "application/x-duckdb",
}


def media_type_for(logical_name: str, explicit: str | None = None) -> str:
    """Media type from suffix, falling back to octet-stream."""
    if explicit:
        return explicit
    return _MEDIA_TYPES.get(Path(logical_name).suffix.lower(), "application/octet-stream")


def artifact_id_for(content_hash: str, artifact_type: str) -> str:
    """Deterministic artifact identity (content + type domain)."""
    return content_id(
        "ARTIFACT", PROVENANCE_SCHEMA_VERSION, {"hash": content_hash, "kind": artifact_type}
    )


def record_artifact(
    content_hash: str,
    size_bytes: int,
    artifact_type: str,
    logical_name: str,
    relative_locator: str,
    created_by_run: str | None = None,
    media_type: str | None = None,
    compression: str | None = None,
    encoding: str | None = None,
) -> ArtifactRef:
    """Build an ArtifactRef (pure constructor; caller persists)."""
    return ArtifactRef(
        artifact_id=artifact_id_for(content_hash, artifact_type),
        artifact_type=artifact_type,
        content_hash=content_hash,
        size_bytes=size_bytes,
        media_type=media_type_for(logical_name, media_type),
        logical_name=logical_name,
        relative_locator=relative_locator,
        created_by_run=created_by_run,
        compression=compression,
        encoding=encoding,
        schema_version=PROVENANCE_SCHEMA_VERSION,
    )


def artifact_from_bytes(
    data: bytes,
    artifact_type: str,
    logical_name: str,
    relative_locator: str,
    created_by_run: str | None = None,
    media_type: str | None = None,
) -> ArtifactRef:
    """Reference in-memory bytes without copying them into the store."""
    return record_artifact(
        hash_bytes(data),
        len(data),
        artifact_type,
        logical_name,
        relative_locator,
        created_by_run,
        media_type,
    )


def artifact_from_file(
    path: str | Path,
    artifact_type: str,
    logical_name: str | None = None,
    relative_locator: str | None = None,
    created_by_run: str | None = None,
    media_type: str | None = None,
) -> ArtifactRef:
    """Streaming reference to an existing file (never loads it fully)."""
    resolved = Path(path)
    content_hash, size = hash_file(resolved)
    name = logical_name or resolved.name
    return record_artifact(
        content_hash,
        size,
        artifact_type,
        name,
        relative_locator or name,
        created_by_run,
        media_type,
    )
