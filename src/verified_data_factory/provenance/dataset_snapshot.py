"""Dataset snapshots (Phase 6, §24–§25).

Identity covers the ordered canonical Golden record content IDs plus
selection metadata — never timestamps, locations, or display names.
Recomputing from the same inputs yields the identical snapshot id
(asserted by test).
"""

from __future__ import annotations

import datetime as _dt

from .hashing import content_id
from .models import PROVENANCE_ENGINE_VERSION, PROVENANCE_SCHEMA_VERSION, DatasetSnapshot


def build_dataset_snapshot(
    golden_content_ids: list[str],
    dataset_name: str,
    dataset_schema_version: str,
    selection_config_id: str,
    quality_engine_version: str,
    created_at: str | None = None,
) -> DatasetSnapshot:
    """Build an immutable, content-defined Golden membership snapshot."""
    ordered = sorted(set(golden_content_ids))
    identity = {
        "golden_record_ids": ordered,
        "selection_config_id": selection_config_id,
        "quality_engine_version": quality_engine_version,
        "provenance_engine_version": PROVENANCE_ENGINE_VERSION,
        "dataset_schema_version": dataset_schema_version,
    }
    return DatasetSnapshot(
        dataset_snapshot_id=content_id("DATASET_SNAPSHOT", PROVENANCE_SCHEMA_VERSION, identity),
        dataset_name=dataset_name,
        dataset_schema_version=dataset_schema_version,
        golden_record_ids=ordered,
        record_count=len(ordered),
        selection_config_id=selection_config_id,
        quality_engine_version=quality_engine_version,
        provenance_engine_version=PROVENANCE_ENGINE_VERSION,
        created_at=created_at or _dt.datetime.now(_dt.UTC).isoformat(),
        schema_version=PROVENANCE_SCHEMA_VERSION,
    )


def recompute_snapshot_id(snapshot: DatasetSnapshot) -> str:
    """Independently recompute a snapshot's identity (replay check)."""
    rebuilt = build_dataset_snapshot(
        list(snapshot.golden_record_ids),
        snapshot.dataset_name,
        snapshot.dataset_schema_version,
        snapshot.selection_config_id,
        snapshot.quality_engine_version,
    )
    return rebuilt.dataset_snapshot_id
