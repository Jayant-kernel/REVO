"""Phase 7 release references for business use (§63).

Experiments, pilots, and offers point at releases by content id — the
manifests themselves stay authoritative in Phase 7. References validate
shape (a `sha256:` content id plus the fields business logic needs)
and visibility: PRIVATE/RESTRICTED releases and PRIVATE_EVAL products
never enter public business exports.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .errors import BusinessConfigError, BusinessValidationError
from .models import BUSINESS_SCHEMA_VERSION


class ReleaseReference(BaseModel):
    """A validated pointer to a Phase 7 release (metadata only)."""

    model_config = {"frozen": True}

    release_id: str = Field(min_length=1)
    dataset_snapshot_id: str = Field(min_length=1)
    product_type: str = Field(min_length=1)
    visibility: str = Field(min_length=1)
    record_count: int = Field(ge=0)
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


def _require_release_id(release_id: str) -> None:
    if not release_id.startswith("sha256:") or len(release_id) <= len("sha256:"):
        raise BusinessValidationError(f"invalid release reference: {release_id!r}")


def reference_release(manifest: dict[str, Any]) -> ReleaseReference:
    """Validate a Phase 7 manifest dict into a business reference (§63)."""
    try:
        release_id = str(manifest["release_id"])
        _require_release_id(release_id)
        return ReleaseReference(
            release_id=release_id,
            dataset_snapshot_id=str(manifest["dataset_snapshot_id"]),
            product_type=str(manifest["product_type"]),
            visibility=str(manifest["visibility"]),
            record_count=int(manifest["record_count"]),
        )
    except BusinessValidationError:
        raise
    except Exception as exc:
        raise BusinessValidationError(f"invalid release manifest: {exc}") from exc


def assert_exportable(reference: ReleaseReference, *, public: bool) -> None:
    """Enforce visibility on business exports (§40, §51, §64).

    PUBLIC/INTERNAL releases may flow anywhere; RESTRICTED releases and
    PRIVATE_EVAL products stay out of public exports.
    """
    if not public:
        return
    if reference.visibility == "RESTRICTED":
        raise BusinessConfigError(
            f"RESTRICTED release {reference.release_id} blocked from public export"
        )
    if reference.product_type == "PRIVATE_EVAL":
        raise BusinessConfigError(
            f"PRIVATE_EVAL product {reference.release_id} blocked from public export"
        )
