"""Public receipt-validation module identity; implementation is offline qualification.

Keep the documented imports and module-level instrumentation seam for callers.
Candidate SQL is executed only through the Phase 3 backend, not this entry point.
"""
import sys
from importlib import import_module

from .qualification.validation import (
    DetailValidator,
    artifact,
    confined,
    digest,
    encode,
    read_json,
    required_sources,
    runtime_identity,
    validate_sources,
)

__all__ = ["DetailValidator", "artifact", "confined", "digest", "encode", "read_json",
           "required_sources", "runtime_identity", "validate_sources"]

sys.modules[__name__] = import_module(".qualification.validation", __package__)
