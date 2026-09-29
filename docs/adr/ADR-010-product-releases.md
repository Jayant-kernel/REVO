# ADR-010 — Product releases are content-defined projections of immutable snapshots

- Status: accepted
- Date: 2026-09-23 (Phase 7)

## Context

Phase 6 made Golden membership immutable and content-addressed
(`DatasetSnapshot`). Phase 7 must turn one snapshot into many
distributable products (train/eval/benchmark) without reopening
correctness (Phase 4), qualification (Phase 5), or provenance (Phase 6)
decisions — and without letting internal data leak into public artifacts
by operator error.

## Decision

1. A release is a pure projection: `Snapshot + Config + Schema + Split
   policy + Format → Release`. The builder reads the snapshot, never
   writes to it.
2. `release_id` covers the canonical payload only (snapshot, config,
   policy, schema, transformation, format, split counts, shard hashes).
   Timestamps, paths, and run ids are excluded, so identical inputs
   rebuild to identical ids (verified by twice-build tests).
3. Visibility is enforced by code: `PUBLIC` releases reject
   `PRIVATE_EVAL` roles, hard contamination flags, and internal-only
   records with explicit reasons. There is no "please remember to
   filter" step.
4. Splits assign isolation groups (never rows) via seeded SHA-256, so
   duplicate/semantic groups cannot straddle splits.
5. The manifest ships the full split plan alongside the shipped count,
   so a release is self-describing even when it carries one split.
6. `metrics.json` and the dataset card reference Phase 5 artifacts;
   Phase 7 computes no quality metrics of its own.

## Rationale

- Content-defined ids make releases citable and deduplicable; excluding
  volatile metadata (per ADR-009) keeps rebuilds stable.
- Code-enforced visibility removes the highest-risk failure mode
  (accidental target/restricted-data exposure) from human procedure.
- Group-level splitting is the only assignment that is simultaneously
  deterministic, leakage-free, and explainable.

## Consequences

- `products.release.build_release` is the single supported build path;
  it self-validates and refuses to emit an `INVALID` release.
- `products.loading.load_release` is the single supported read path;
  it re-validates on every load.
- Product names are part of config identity: renaming a product is a
  new release, not an alias.
- Phase 8 (commercialization) consumes releases; it may not rebuild
  project internals.

## Alternatives considered

- Name/alias-based release identity: rejected (citations would rot when
  directories move).
- Row-level random splitting with a seed: rejected (duplicates straddle
  splits; leakage risk).
- Recomputing quality metrics at build time: rejected (dual sources of
  truth with Phase 5; authority violation).
