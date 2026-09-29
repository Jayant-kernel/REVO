# ADR-003 — Open-weight models are the initial generation source

- Status: accepted
- Date: 2026-09-23 (Phase 0)

## Context

Candidate solutions must come from models whose licensing permits the
intended commercial data workflow, with reproducible revisions.

## Decision

Initial generation source is **open-weight models**, planned:
`Qwen3-Coder-30B-A3B-Instruct`, `Devstral-Small-2-24B-Instruct-2512`,
optionally `Qwen3-30B-A3B-Thinking-2507` as reasoning/teacher.
No integration in Phase 0.

## Rationale

- Self-hostable: pinned revisions, reproducible sampling, no API drift.
- Cost control for large candidate volumes.
- Provenance-friendly (record exact revision per candidate).

## Consequences

- Phase 2 must record per-model license/provenance before any use
  (see `docs/licensing.md`).
- Model-adapter abstraction required so models are swappable.

## Alternatives considered

- Closed APIs: rejected as primary source (terms risk, non-reproducibility, cost).
- Human-written solutions only: valuable for seeding, but doesn't scale generation.
