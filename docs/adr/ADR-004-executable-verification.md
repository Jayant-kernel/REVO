# ADR-004 — Executable verification is preferred over LLM judging

- Status: accepted
- Date: 2026-09-23 (Phase 0)

## Context

A data factory must decide correctness. Options: LLM judges, execution
against oracles/tests, or hybrids.

## Decision

**Executable, deterministic validation is the primary correctness mechanism**
(independent oracle + hidden/property/metamorphic tests + mutation-scored
suites). LLM judging is at most auxiliary, never the verdict.

## Rationale

- "LLM judges LLM" compounds errors and is non-reproducible.
- SQL admits ground truth by execution: run candidate vs. oracle on fixtures.
- Executable evidence is auditable and commercially defensible.

## Consequences

- Verification layer (Phase 4) is the most engineering-heavy layer after tasks.
- Test-suite strength must itself be measured (mutation testing).

## Alternatives considered

- LLM-as-judge primary: rejected for correctness (allowed later only for
  auxiliary quality signals like ambiguity detection).
