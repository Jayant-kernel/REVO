"""Visibility-aware Golden selection for products (§40).

Wraps Phase 5 Golden decisions with product visibility enforcement:
records the visibility policy forbids are excluded with explicit
reasons — enforced by code, never by operator discipline.
"""

from __future__ import annotations

from typing import Any

from verified_data_factory.quality.models import GoldenRecord

from .models import Visibility
from .profiles import check_record_dict_visible


def select_visible_records(
    golden_records: list[GoldenRecord],
    quality_by_id: dict[str, dict[str, Any]],
    visibility: Visibility,
) -> tuple[list[GoldenRecord], list[tuple[str, list[str]]]]:
    """Split Golden records into (allowed, [(candidate_id, reasons)]).

    ``quality_by_id`` maps candidate_id → RecordQuality dict (for role,
    contamination flags, internal-only markers).
    """
    allowed: list[GoldenRecord] = []
    rejected: list[tuple[str, list[str]]] = []
    for golden in sorted(golden_records, key=lambda g: g.candidate_id):
        quality = quality_by_id.get(golden.candidate_id, {})
        reasons = check_record_dict_visible(quality, visibility)
        if reasons:
            rejected.append((golden.candidate_id, reasons))
        else:
            allowed.append(golden)
    return allowed, rejected
