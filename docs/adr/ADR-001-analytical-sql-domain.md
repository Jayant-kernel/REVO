# ADR-001 — Initial domain is analytical SQL

- Status: accepted
- Date: 2026-09-23 (Phase 0)

## Context

The factory needs one initial domain to prove the generate → execute →
verify → curate loop before generalizing. Candidates: analytical SQL,
Python data-wrangling, general code tasks.

## Decision

The initial domain is **analytical SQL** (SELECT-heavy analytics:
JOINs, aggregation, CTEs, subqueries, window functions, date/time,
dedup, retention, funnel/session analysis).

## Rationale

- Executable verification is cheap and deterministic (run query, compare results).
- Fixtures are compact and seedable; edge cases (NULLs, ties, dupes) are easy to construct.
- Direct commercial demand from SQL/data/analytics agents.

## Consequences

- Phase 1 task families are SQL-only; abstractions must not hard-code SQL
  forever, but SQL comes first.
- Oracle design assumes result-set comparison semantics.

## Alternatives considered

- Python/pandas tasks: richer, but heavier sandbox + flakier oracles.
- Multi-language from day one: rejected — proves nothing fast, complicates verification.
