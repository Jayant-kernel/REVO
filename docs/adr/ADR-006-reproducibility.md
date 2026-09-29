# ADR-006 — Reproducibility is a first-class requirement

- Status: accepted
- Date: 2026-09-23 (Phase 0)

## Context

Commercial data requires provenance: buyers and auditors must be able to
recreate any record and its verdict.

## Decision

Every task instance and verdict must be reproducible from pinned
(template version, seed, oracle/test-suite versions, container digest,
model revision). Versions are immutable; "latest" is never referenced
in stored records.

## Rationale

- Debugging, auditing, and regression-gating all require replay.
- Cost-per-verified-example is meaningless if runs aren't comparable.

## Consequences

- Seeded fixture generation; immutable TaskVersion/TestSuite/VerificationRun.
- Provenance layer (Phase 6) enforces the metadata chain.

## Alternatives considered

- Best-effort logging: rejected — insufficient for commercial provenance.
