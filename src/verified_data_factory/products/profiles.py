"""Product profiles and visibility enforcement (§7, §9, §40).

Profiles decide which fields each product carries; visibility is enforced
by code — a PUBLIC release rejects restricted records instead of trusting
the operator to filter them.
"""

from __future__ import annotations

from typing import Any, Literal

from .errors import ProductConfigError
from .models import ProductType, Visibility

ProfileName = Literal["TRAIN", "PUBLIC_EVAL", "PRIVATE_EVAL", "BENCHMARK", "SAMPLE"]

# dataset_role values that may never appear in a PUBLIC product.
PUBLIC_FORBIDDEN_ROLES = frozenset({"PRIVATE_EVAL"})

# RecordQuality contamination flag types treated as hard restrictions.
RESTRICTED_FLAG_TYPES = frozenset({"CONTAMINATION_RESTRICTED"})


class ProductProfile:
    """Field-exposure policy for one product type (plain data holder)."""

    def __init__(
        self,
        name: ProfileName,
        include_sql_target: bool,
        include_verification_summary: bool,
        include_provenance_refs: bool,
        include_audit: bool,
        allowed_roles: frozenset[str],
    ) -> None:
        self.name = name
        self.include_sql_target = include_sql_target
        self.include_verification_summary = include_verification_summary
        self.include_provenance_refs = include_provenance_refs
        self.include_audit = include_audit
        self.allowed_roles = allowed_roles


PROFILES: dict[str, ProductProfile] = {
    # Training: full input+target, provenance by reference only.
    "TRAIN": ProductProfile("TRAIN", True, False, True, False, frozenset({"TRAIN", "UNKNOWN"})),
    # Public eval: question + schema; target SQL withheld by default.
    "PUBLIC_EVAL": ProductProfile(
        "PUBLIC_EVAL", False, False, True, False, frozenset({"TRAIN", "UNKNOWN"})
    ),
    # Private eval: internal only; may carry targets + verification summaries.
    "PRIVATE_EVAL": ProductProfile(
        "PRIVATE_EVAL",
        True,
        True,
        True,
        True,
        frozenset({"TRAIN", "PRIVATE_EVAL", "UNKNOWN"}),
    ),
    # Benchmark: repeatable items; target exposure follows include_sql_target.
    "BENCHMARK": ProductProfile(
        "BENCHMARK", True, False, True, False, frozenset({"TRAIN", "UNKNOWN"})
    ),
    # Sample: tiny public-safe preview of the training shape.
    "SAMPLE": ProductProfile("SAMPLE", True, False, False, False, frozenset({"TRAIN", "UNKNOWN"})),
}


def get_profile(name: str) -> ProductProfile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ProductConfigError(f"unknown product profile: {name!r}") from exc


def profile_for_type(product_type: ProductType) -> ProductProfile:
    return get_profile(product_type)


def check_record_visible(
    *,
    role: str,
    contamination_hard: bool,
    visibility: Visibility,
    internal_only: bool = False,
) -> list[str]:
    """Visibility gate; returns violation reasons (empty means allowed)."""
    if visibility != "PUBLIC":
        return []
    violations: list[str] = []
    if role in PUBLIC_FORBIDDEN_ROLES:
        violations.append(f"role {role} forbidden in PUBLIC releases")
    if contamination_hard:
        violations.append("hard contamination flag forbidden in PUBLIC releases")
    if internal_only:
        violations.append("INTERNAL_ONLY record forbidden in PUBLIC releases")
    return violations


def check_record_dict_visible(record: dict[str, Any], visibility: Visibility) -> list[str]:
    """Dict-shaped variant used by split/selection guards."""
    flags = record.get("contamination_flags", []) or []
    return check_record_visible(
        role=str(record.get("role", "UNKNOWN")),
        contamination_hard=any(bool(f.get("hard")) for f in flags if isinstance(f, dict)),
        visibility=visibility,
        internal_only=bool(record.get("internal_only", False)),
    )
