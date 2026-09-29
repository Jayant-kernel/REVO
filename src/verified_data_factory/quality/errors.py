"""Quality exceptions (Phase 5).

Analysis outcomes (exclusions, flags, audit states) are returned as data,
never raised. Exceptions here signal programming or configuration errors.
"""

from __future__ import annotations


class QualityError(Exception):
    """Base error for quality harness failures."""


class QualityConfigError(QualityError):
    """Invalid quality configuration."""


class RecordError(QualityError):
    """Malformed verified-record bundle."""
