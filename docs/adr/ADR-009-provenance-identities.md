# ADR-009 — Content-addressed provenance with operational metadata kept out of identities

- Status: accepted
- Date: 2026-09-23 (Phase 6)

## Context

Golden records need traceability (where did this come from?) and
reproducibility evidence (what would replay need?). Run metadata —
timestamps, durations, unique run ids — is operationally necessary but
would destroy content determinism if hashed into identities.

## Decision

1. Content IDs (`sha256:<hex>`) cover identity-bearing payloads only,
   with explicit domain separation per node type.
2. Volatile run identifiers (`execution_id` embeds a timestamp;
   `verification_id` derives from it) and timestamps/durations are
   excluded from hashed payloads by construction. They remain
   retrievable in raw artifacts and operational activities.
3. Corrections are new records linked by `SUPERSEDES`, never rewrites
   (the store rejects same-id/different-content appends).
4. Reproducibility is reported per layer with honest ceilings:
   generation is CONDITIONAL at best for nondeterministic stacks, and
   the overall status is the worst layer status.

## Rationale

- Hashing run metadata would make every rerun a "different" dataset,
  defeating the purpose of content addressing.
- Excluding fields silently would be dishonest; the payload schemas
  document the boundary instead.
- Append-only history matches audit requirements better than mutable
  records with edit logs.

## Consequences

- `provenance.canonical` is the single serialization mechanism; no
  ad-hoc `json.dumps()` in the package.
- Two runs of the same inputs yield identical content ids, snapshot
  ids, and manifest identities; only operational ids differ.
- Model nondeterminism is represented (`deterministic_replay: false`
  by default) rather than assumed away.

## Alternatives considered

- Hashing everything including timestamps: rejected (destroys
  determinism, the core requirement).
- Mutable store with updates: rejected (audit trail must be append-only).
- Single global reproducibility boolean: rejected (hides which layer
  is actually unpinned).
