"""Verification exceptions (Phase 4).

Stage outcomes (mismatch, timeout, oracle crash) are returned as
``VerificationResult`` data, never raised. Exceptions here signal
programming or configuration errors only.
"""

from __future__ import annotations


class VerificationError(Exception):
    """Base error for verification harness failures."""


class VerificationConfigError(VerificationError):
    """Invalid verification configuration."""


class OracleError(VerificationError):
    """Oracle registry or oracle contract violation."""


class OracleUnknownError(OracleError):
    """No oracle registered for (template_id, version)."""


class BackendError(VerificationError):
    """Candidate-execution backend failure (infrastructure, not verdict)."""
