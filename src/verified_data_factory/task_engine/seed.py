"""Deterministic seed handling and task identity (Phase 1).

Seed-replay contract::

    same template ID + same template version + same generation config
    + same seed + same Task Engine version
    = same canonical TaskInstance

All randomness derives from the task seed. Child streams (one per table)
are derived via SHA-256 so table generators stay independent yet
deterministic. No global ``random`` state is used.

``ENGINE_VERSION`` names the Task Engine behavior contract: any change to
generation behavior that can alter task semantics, fixture values, row
counts, edge-case injection, instruction rendering, or task identity
requires bumping it (and documenting the break). See
``docs/phase-1-contract.md`` for the logical-vs-environment
reproducibility boundary.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from typing import Any

ENGINE_VERSION = "1.0.0"

_IDENTITY_HASH_CHARS = 12  # 48 bits: collision-resistant for millions of tasks


def derive_child_seed(parent_seed: int, stream: str) -> int:
    """Derive a deterministic child seed from ``(parent_seed, stream)``."""
    digest = hashlib.sha256(f"{parent_seed}:{stream}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def make_rng(seed: int) -> random.Random:
    """Return an isolated ``random.Random`` for ``seed``."""
    return random.Random(seed)


def task_identity_string(
    template_id: str,
    template_version: int,
    config: Mapping[str, Any],
    seed: int,
    engine_version: str = ENGINE_VERSION,
) -> str:
    """Canonical identity payload for task generation inputs.

    Key order and config ordering are normalized (``sort_keys=True``), so the
    identity is independent of dictionary ordering.
    """
    payload = {
        "config": dict(config),
        "engine_version": engine_version,
        "seed": seed,
        "template_id": template_id,
        "template_version": template_version,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def build_task_id(
    template_id: str,
    template_version: int,
    seed: int,
    config: Mapping[str, Any] | None = None,
    engine_version: str = ENGINE_VERSION,
) -> str:
    """Build a stable, collision-resistant task id.

    Format: ``{template_id}.v{version}.{12-hex-hash}``, e.g.
    ``sql.retention.30_day.v1.9f3a2c1e7b44``. The suffix is the leading
    12 hex chars of SHA-256 over the canonical identity payload
    (template id, version, generation config, seed, engine version), so
    distinct semantic inputs give distinct ids at any scale — unlike a
    ``seed % 1M`` suffix, which collides for seeds 1M apart and ignores
    version/config entirely.

    Human-readable inputs (``seed``, ``template_id``, ``template_version``,
    config) remain separately stored fields on ``TaskInstance``.
    """
    if seed < 0:
        raise ValueError("seed must be non-negative")
    digest = hashlib.sha256(
        task_identity_string(
            template_id, template_version, config or {}, seed, engine_version
        ).encode()
    ).hexdigest()[:_IDENTITY_HASH_CHARS]
    return f"{template_id}.v{template_version}.{digest}"
