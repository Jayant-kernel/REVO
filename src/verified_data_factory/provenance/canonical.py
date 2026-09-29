"""One canonical serialization mechanism (Phase 6, §8).

Contract (also documented in docs/provenance-model.md):

* mappings: keys sorted by Unicode code point; ``sort_keys=True`` always.
* lists/tuples: order preserved (tuples become lists).
* sets/frozensets: normalized to sorted canonical forms, tagged so an
  empty set cannot collide with an empty list.
* strings: NFC-normalized, emitted as UTF-8 (``ensure_ascii=False``).
* booleans/nulls: JSON literals (booleans never coerce to numbers).
* integers: exact. floats: finite only (NaN/±Infinity raise), shortest
  round-trip representation via ``repr``.
* decimals: tagged ``{"$decimal": "<str>"}`` so ``1.0`` (float) never
  collides with ``Decimal("1.0")``.
* datetimes/dates/times: tagged ``{"$datetime": "<iso>"}``.
* bytes: tagged ``{"$bytes": "<hex>"}``.
* enums: their ``.value``.
* Pydantic models: ``model_dump(mode="json")`` then normalized.
* anything else: raise :class:`CanonicalizationError` (no silent repr()).

Newlines are normalized to ``\\n`` in the final UTF-8 encoding. The same
function backs hashing, manifests, IDs, fingerprints, and snapshots —
no ad-hoc ``json.dumps()`` calls exist in the provenance package.
"""

from __future__ import annotations

import datetime as _dt
import enum
import json
import math
import unicodedata
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from .errors import CanonicalizationError


def normalize(value: Any) -> Any:
    """Normalize an arbitrary value to canonical JSON-compatible form."""
    if value is None or isinstance(value, (bool, int, str)):
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalizationError(f"non-finite float: {value!r}")
        return value
    if isinstance(value, Decimal):
        return {"$decimal": format(value, "f")}
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return {"$datetime": value.isoformat()}
    if isinstance(value, (bytes, bytearray)):
        return {"$bytes": bytes(value).hex()}
    if isinstance(value, enum.Enum):
        return normalize(value.value)
    if isinstance(value, BaseModel):
        return normalize(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(normalize(k)): normalize(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return {"$set": sorted(json.dumps(normalize(v), sort_keys=True) for v in value)}
    raise CanonicalizationError(f"no canonical form for type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Deterministic JSON string for hashing, IDs, and manifests."""
    normalized = normalize(value)
    text = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def canonical_bytes(value: Any) -> bytes:
    """UTF-8 encoding of :func:`canonical_json`."""
    return canonical_json(value).encode("utf-8")
