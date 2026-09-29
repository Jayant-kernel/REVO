# ADR-007 — Chain-of-Thought is not required in the core dataset schema

- Status: accepted
- Date: 2026-09-23 (Phase 0)

## Context

Whether to store model reasoning traces alongside verified solutions.

## Decision

Chain-of-Thought is **not** a mandatory core field of the Golden Record.
The schema centers on verified correctness (task, solution, verification
evidence, quality, provenance). An optional concise explanation may be
added later.

## Rationale

- Value proposition is correctness evidence, not private traces.
- Mandatory CoT raises license/privacy/safety costs and invites gaming
  (traces optimized for appearance rather than truth).

## Consequences

- Golden Record keeps CoT out of the required path (see `docs/golden-record.md`).
- Preference/RL products can add opt-in rationale fields if experiments
  show value.

## Alternatives considered

- Mandatory CoT: rejected (cost without proven commercial lift).
