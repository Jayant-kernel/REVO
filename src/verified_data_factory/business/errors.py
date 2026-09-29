"""Business-layer errors (Phase 8).

Measurement/validation outcomes (unsupported claims, failed pilots,
hypothesis verdicts) are returned as data, never raised. Exceptions
here signal programming, configuration, or I/O errors only.
"""

from __future__ import annotations


class BusinessError(Exception):
    """Base error for business-harness failures."""


class BusinessConfigError(BusinessError):
    """Invalid experiment, benchmark, economics, or GTM configuration."""


class BusinessValidationError(BusinessError):
    """An artifact failed structural validation during loading or recording."""


class BusinessIOError(BusinessError):
    """Filesystem read/write failure while building or loading artifacts."""


class ClaimUnsupportedError(BusinessError):
    """Raised only by strict claim-check helpers; validators return data."""
