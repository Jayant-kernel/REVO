# ADR-008 — Golden selection is dataset-aware, deterministic, and evidence-preserving

- Status: accepted
- Date: 2026-09-23 (Phase 5)

## Context

Phase 4 proves per-candidate correctness, but a commercial dataset needs
dataset-level judgment: duplicates, balance, contamination, and audit.
The question is how the Golden selector may use that judgment without
becoming an opaque score or re-judging correctness.

## Decision

1. Verification PASS is necessary but never sufficient for GOLDEN.
2. Selection applies hard evidence gates first, then dataset-aware rules
   (one survivor per duplicate group, family quotas), all deterministic
   over candidate_id ordering with explicit seeds.
3. Every non-GOLDEN outcome keeps machine-readable reasons; the underlying
   Phase 4 evidence is never modified.
4. Exported artifacts are byte-identical across runs (volatile telemetry
   projected out; no timestamps in decisions).

## Rationale

- Separates "correct" (Phase 4, authoritative) from "dataset-worthy"
  (Phase 5, policy) so either can evolve without invalidating the other.
- Explainability is a commercial requirement: buyers and auditors need
  reasons, not scores.
- Determinism makes selection auditable and regression-testable.

## Consequences

- `quality/` owns selection policy via `QualityConfig`; later phases
  consume `golden.jsonl` + `dataset_health.json` as stable inputs.
- Equivalent mutants and weak suites gate through INCONCLUSIVE/WEAK paths
  rather than silent inclusion.
- NOT_APPLICABLE mutation status is explicitly not a perfect score.

## Alternatives considered

- Single quality score: rejected (hides reasons, untestable thresholds).
- Re-verifying inside Phase 5: rejected (duplicates authority, wastes
  sandbox cycles).
- LLM judge for ambiguity/quality: rejected per ADR-004's principle;
  deterministic structural signals only.
