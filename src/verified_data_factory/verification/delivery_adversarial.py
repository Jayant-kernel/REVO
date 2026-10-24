"""Hand-authored public-contract delivery cases, not generator/witness derivatives.

These synthetic examples are separately authored fixtures, not heldout data or
evidence of an independent human author. Expected rows and business rationale
live in tests/test_delivery_adversarial.py and the workstream-a evidence pack.
"""
from __future__ import annotations

from typing import Any


def delivery_adversarial(
    template_id: str, template_version: int = 1,
) -> dict[str, list[dict[str, Any]]] | None:
    """Return fresh tables only for the five exact public version-1 contracts."""
    if template_version != 1:
        return None
    if template_id == "sql.dedup.lowest_quote":
        return {"quotes": [
            {"part": "axle", "supplier": "alpha", "price_cents": 430},
            {"part": "axle", "supplier": "Zulu", "price_cents": 430},
            {"part": "axle", "supplier": "Zulu", "price_cents": 430},
            {"part": "axle", "supplier": "", "price_cents": None},
            {"part": "axle", "supplier": "Budget", "price_cents": 900},
            {"part": "unknown", "supplier": "Only", "price_cents": None},
            {"part": "", "supplier": "", "price_cents": 0},
            {"part": "ceiling", "supplier": "Solo", "price_cents": 2147483647},
        ]}
    if template_id == "sql.joins.requested_language_titles":
        return {
            "requests": [
                {"request_id": 71, "item_id": 801, "language": "pt"},
                {"request_id": 71, "item_id": 801, "language": "pt"},
                {"request_id": 72, "item_id": 801, "language": "PT"},
                {"request_id": 73, "item_id": None, "language": "pt"},
                {"request_id": 74, "item_id": 802, "language": None},
                {"request_id": 75, "item_id": 803, "language": ""},
            ],
            "translations": [
                {"item_id": 801, "language": "pt", "title": "Mar"},
                {"item_id": 801, "language": "pt", "title": "Mar"},
                {"item_id": 801, "language": "pt", "title": None},
                {"item_id": 801, "language": "en", "title": "Sea"},
                {"item_id": None, "language": "pt", "title": "Null item trap"},
                {"item_id": 802, "language": None, "title": "Null language trap"},
                {"item_id": 803, "language": "", "title": ""},
                {"item_id": 999, "language": "pt", "title": "Orphan"},
            ],
        }
    if template_id == "sql.subqueries.pareto_shipping":
        return {"options": [
            {"option_id": 81, "lane": "dock", "cost_cents": 40, "duration_minutes": 90},
            {"option_id": 82, "lane": "dock", "cost_cents": 40, "duration_minutes": 90},
            {"option_id": 83, "lane": "dock", "cost_cents": 40, "duration_minutes": 100},
            {"option_id": 84, "lane": "dock", "cost_cents": 70, "duration_minutes": 60},
            {"option_id": 85, "lane": "dock", "cost_cents": None, "duration_minutes": 0},
            {"option_id": 86, "lane": "DOCK", "cost_cents": 100, "duration_minutes": 100},
            {"option_id": 87, "lane": "dock", "cost_cents": 0, "duration_minutes": None},
            {"option_id": 88, "lane": "", "cost_cents": 0, "duration_minutes": 0},
        ]}
    if template_id == "sql.retention.renewal_coverage":
        return {
            "episodes": [
                {"episode_id": 91, "member_id": 501, "expires_at": "2025-12-28T06:30:00"},
                {"episode_id": 92, "member_id": 502, "expires_at": "2025-07-04T12:00:00.000001"},
                {"episode_id": 93, "member_id": 503, "expires_at": "2025-07-04T12:00:00"},
                {"episode_id": 94, "member_id": 504, "expires_at": "2025-07-04T12:00:00"},
                {"episode_id": 95, "member_id": 501, "expires_at": "2025-12-27T06:30:00"},
                {"episode_id": 96, "member_id": 501, "expires_at": "2026-01-01T00:00:00"},
            ],
            "renewals": [
                {"member_id": 501, "begins_at": "2024-12-01T00:00:00", "ends_at": "2026-01-11T06:30:00", "status": "confirmed"},
                {"member_id": 501, "begins_at": "2024-12-01T00:00:00", "ends_at": "2026-01-11T06:30:00", "status": "confirmed"},
                {"member_id": 502, "begins_at": "2025-07-01T00:00:00", "ends_at": "2025-07-18T12:00:00", "status": "confirmed"},
                {"member_id": 503, "begins_at": "2025-07-04T12:00:00", "ends_at": "2025-07-11T12:00:00", "status": "confirmed"},
                {"member_id": 503, "begins_at": "2025-07-11T12:00:00", "ends_at": "2025-07-18T12:00:00", "status": "confirmed"},
                {"member_id": 504, "begins_at": "2025-07-01T00:00:00", "ends_at": "2025-08-01T00:00:00", "status": "pending"},
            ],
        }
    if template_id == "sql.windows.queue_batches":
        return {"submissions": [
            {"submission_id": 116, "queue": "intake", "submitted_at": None},
            {"submission_id": 112, "queue": "intake", "submitted_at": "2025-02-01T00:00:00"},
            {"submission_id": 114, "queue": "intake", "submitted_at": "2026-02-01T00:00:00"},
            {"submission_id": 111, "queue": "intake", "submitted_at": "2024-02-01T00:00:00"},
            {"submission_id": 115, "queue": "intake", "submitted_at": None},
            {"submission_id": 113, "queue": "intake", "submitted_at": "2025-02-01T00:00:00"},
            {"submission_id": 110, "queue": "intake", "submitted_at": "2023-02-01T00:00:00"},
            {"submission_id": 118, "queue": "Intake", "submitted_at": None},
            {"submission_id": 117, "queue": "Intake", "submitted_at": None},
            {"submission_id": 119, "queue": "", "submitted_at": None},
        ]}
    return None
