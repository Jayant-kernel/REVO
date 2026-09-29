"""Activities, run manifests, and configuration snapshots (Phase 6, §12–§13, §39).

Activities are operational records (unique run ids, timestamps) kept
strictly separate from content identities. Configuration snapshots are
content-addressed — a path is never stored in place of content.
"""

from __future__ import annotations

import datetime as _dt
import uuid
from typing import Any

from .canonical import canonical_bytes
from .hashing import content_id, hash_bytes
from .models import (
    PROVENANCE_ENGINE_VERSION,
    PROVENANCE_SCHEMA_VERSION,
    ActivityStatus,
    ActivityType,
    ConfigSnapshot,
    ProvenanceActivity,
    RunManifest,
)


def utc_now_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


def new_run_id() -> str:
    """Unique operational run id (never part of a content identity)."""
    return "run-" + uuid.uuid4().hex[:16]


def start_activity(
    activity_type: ActivityType,
    tool_version: str,
    configuration_id: str | None = None,
    source_snapshot_id: str | None = None,
    environment_snapshot_id: str | None = None,
) -> ProvenanceActivity:
    """Open an operational activity record."""
    now = utc_now_iso()
    return ProvenanceActivity(
        run_id=new_run_id(),
        activity_type=activity_type,
        tool_version=tool_version,
        schema_version=PROVENANCE_SCHEMA_VERSION,
        configuration_id=configuration_id,
        source_snapshot_id=source_snapshot_id,
        environment_snapshot_id=environment_snapshot_id,
        status="SUCCEEDED",
        started_at=now,
        finished_at=now,
    )


def finish_activity(activity: ProvenanceActivity, status: ActivityStatus) -> ProvenanceActivity:
    """Close an activity with its outcome (returns a new record)."""
    return activity.model_copy(update={"status": status, "finished_at": utc_now_iso()})


def snapshot_config(config_name: str, content: Any, schema_version: str) -> ConfigSnapshot:
    """Content-address one configuration mapping."""
    from .canonical import normalize

    canonical_content = normalize(content)
    if not isinstance(canonical_content, dict):
        raise TypeError("configuration content must normalize to a mapping")
    blob = canonical_bytes(canonical_content)
    digest = hash_bytes(blob)
    return ConfigSnapshot(
        configuration_id=content_id("CONFIGURATION", schema_version, canonical_content),
        config_name=config_name,
        content_hash=digest,
        schema_version=schema_version,
        content=canonical_content,
    )


def build_run_manifest(
    run_id: str,
    factory_version: str,
    phase: str,
    schema_versions: dict[str, str],
    source_snapshot_id: str,
    dependency_lock_hash: str,
    environment_snapshot_id: str | None,
    started_at: str,
    finished_at: str,
) -> RunManifest:
    """Build a manifest whose id covers the deterministic subset only."""
    identity = {
        "factory_version": factory_version,
        "provenance_engine_version": PROVENANCE_ENGINE_VERSION,
        "phase": phase,
        "schema_versions": schema_versions,
        "source_snapshot_id": source_snapshot_id,
        "dependency_lock_hash": dependency_lock_hash,
        "environment_snapshot_id": environment_snapshot_id,
    }
    return RunManifest(
        manifest_id=content_id("RUN_MANIFEST", PROVENANCE_SCHEMA_VERSION, identity),
        run_id=run_id,
        factory_version=factory_version,
        provenance_engine_version=PROVENANCE_ENGINE_VERSION,
        phase=phase,
        schema_versions=schema_versions,
        source_snapshot_id=source_snapshot_id,
        dependency_lock_hash=dependency_lock_hash,
        environment_snapshot_id=environment_snapshot_id,
        started_at=started_at,
        finished_at=finished_at,
        schema_version=PROVENANCE_SCHEMA_VERSION,
    )
