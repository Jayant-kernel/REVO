# ADR-002 — DuckDB is the initial execution engine

- Status: accepted
- Date: 2026-09-23 (Phase 0)

## Context

Need one SQL engine for fixtures, oracles, and verification in Phase 1–4.

## Decision

**DuckDB** is the initial execution engine.

## Rationale

- Embedded, zero-server: trivial to run in tests, CI, and sandboxes.
- Strong analytical SQL coverage (CTEs, window functions, date/time).
- Deterministic local execution suits reproducible fixtures.

## Consequences

- Fixtures and oracles target DuckDB dialect first.
- Dialect-portability (Postgres/Spark) is deferred, not excluded.

## Alternatives considered

- PostgreSQL: more production-realistic, but heavier to provision per-run.
- SQLite: lighter, but weaker analytical function support.
