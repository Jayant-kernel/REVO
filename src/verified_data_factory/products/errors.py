"""Product errors (Phase 7).

Build/validation outcomes (failed checks, rejected records) are returned
as data, never raised. Exceptions here signal programming, configuration,
or I/O errors only.
"""

from __future__ import annotations


class ProductError(Exception):
    """Base error for product harness failures."""


class ProductConfigError(ProductError):
    """Invalid product or split configuration."""


class ProductValidationError(ProductError):
    """A release artifact failed structural validation during loading."""


class ProductIOError(ProductError):
    """Filesystem read/write failure while building or loading a release."""
