"""Phase 4 entry points (thin by design; orchestration lives in verifier)."""

from .verifier import build_verification_id, compute_oracle, verify_candidate

__all__ = ["build_verification_id", "compute_oracle", "verify_candidate"]
