# ADR-005 — Task specifications are authoritative over natural-language prompts

- Status: accepted
- Date: 2026-09-23 (Phase 0)

## Context

Each record pairs a natural-language instruction with a formal task
definition. When they disagree, one must win.

## Decision

The **structured task specification** (schema + fixture contract + oracle +
tests) is authoritative. The natural-language prompt is a rendering of it.

## Rationale

- Prompts are ambiguous; specs are executable.
- Verification can only ground truth against the spec.
- Ambiguity detection (Quality layer) needs a reference to flag prompt/spec drift.

## Consequences

- Task DSL + registry design (Phase 1) must make specs first-class.
- Instruction generation is a deterministic function of the spec + version.

## Alternatives considered

- Prompt-authoritative: rejected — makes verification subjective.
