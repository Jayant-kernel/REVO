"""Data Products (Phase 7 public API).

Transforms immutable Golden snapshots into versioned, validated,
distributable train/eval/benchmark products. Packaging only — Phase 4
owns correctness, Phase 5 owns Golden qualification, Phase 6 owns
provenance.
"""

from .api import *
from .api import __all__  # noqa: F401
