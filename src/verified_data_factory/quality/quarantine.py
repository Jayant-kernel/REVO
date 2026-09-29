"""Deterministic quarantine for Golden selection (audit/remediation layer).

Quarantine demotes records before dedup/quotas run, so a quarantined
representative can never displace a healthy group member. Historical
artifacts are never modified: quarantine is an explicit selection
input, recorded as machine-readable reasons on the affected records.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from .errors import QualityConfigError

QUARANTINE_SCHEMA_VERSION = "1.0"


class QuarantineEntry(BaseModel):
    """One quarantined record with its persisted rationale."""

    model_config = {"frozen": True}

    candidate_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    applicable_mutants: int = Field(ge=0)
    mutation_score: float | None = None
    original_decision: str = Field(min_length=1)
    release_eligible: bool = False
    schema_version: str = Field(default=QUARANTINE_SCHEMA_VERSION, min_length=1)


def load_quarantine(path: str | Path) -> list[QuarantineEntry]:
    """Load a quarantine list (JSON array, deterministic order)."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise QualityConfigError(f"malformed quarantine file {path}: {exc}") from exc
    if not isinstance(payload, list):
        raise QualityConfigError(f"quarantine file {path} must be a JSON array")
    try:
        entries = [QuarantineEntry.model_validate(row) for row in payload]
    except Exception as exc:
        raise QualityConfigError(f"invalid quarantine entry in {path}: {exc}") from exc
    return sorted(entries, key=lambda e: e.candidate_id)


def quarantine_map(entries: list[QuarantineEntry]) -> dict[str, QuarantineEntry]:
    """candidate_id → entry (deterministic; duplicates collapse to first)."""
    merged: dict[str, QuarantineEntry] = {}
    for entry in sorted(entries, key=lambda e: e.candidate_id):
        merged.setdefault(entry.candidate_id, entry)
    return merged


def write_quarantine_artifact(entry: QuarantineEntry, path: str | Path) -> Path:
    """Persist one quarantine record; the historical record stays untouched."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(entry.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def quarantined_ids(entries: list[QuarantineEntry]) -> set[str]:
    """Ids ineligible for release (release_eligible False)."""
    return {e.candidate_id for e in entries if not e.release_eligible}
