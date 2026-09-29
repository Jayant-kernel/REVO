"""Content identities and artifact hashing (Phase 6, §7 + §9).

Every content ID has the form ``sha256:<hex>`` over
``canonical_json({"type": ..., "schema_version": ..., "payload": ...})``,
giving domain separation across node types for free. Timestamps and other
operational fields must be excluded from payloads by callers — hashing
never strips fields silently.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, BinaryIO

from .canonical import canonical_bytes

_CHUNK_SIZE = 65536


def content_id(node_type: str, schema_version: str, payload: Any) -> str:
    """Deterministic ``sha256:<hex>`` identity for a versioned payload."""
    envelope = {"type": node_type, "schema_version": schema_version, "payload": payload}
    return "sha256:" + hashlib.sha256(canonical_bytes(envelope)).hexdigest()


def hash_bytes(data: bytes) -> str:
    """Content hash of in-memory bytes (``sha256:<hex>``)."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def hash_stream(stream: BinaryIO, chunk_size: int = _CHUNK_SIZE) -> tuple[str, int]:
    """Streaming SHA-256 over a binary stream. Returns (hash, size_bytes)."""
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    return "sha256:" + digest.hexdigest(), size


def hash_file(path: str | Path, chunk_size: int = _CHUNK_SIZE) -> tuple[str, int]:
    """Streaming SHA-256 over a file. Returns (hash, size_bytes)."""
    with open(path, "rb") as fh:
        return hash_stream(fh, chunk_size)
