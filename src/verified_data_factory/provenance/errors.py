"""Provenance exceptions (Phase 6).

Analysis outcomes (incomplete lineage, failed validation, conditional
reproducibility) are returned as data, never raised. Exceptions here
signal programming, configuration, or store-integrity errors only.
"""

from __future__ import annotations


class ProvenanceError(Exception):
    """Base error for provenance harness failures."""


class ProvenanceConfigError(ProvenanceError):
    """Invalid provenance configuration."""


class StoreError(ProvenanceError):
    """Provenance store integrity violation (conflicts, bad references)."""


class CanonicalizationError(ProvenanceError):
    """A value cannot be represented canonically (NaN, unknown type)."""
