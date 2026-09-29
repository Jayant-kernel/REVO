# Human Audit

Status: **implemented** (Phase 5, sampling + JSONL results — no UI).

## Principle

Review effort follows risk. Most records never need a human; the ones
that do are chosen deterministically, and every decision is recorded
against the sampled item.

## Risk signals (configurable weights)

- Ambiguous task (+2), weak verification (+3), survived mutants (+2),
  soft contamination (+3), rare family (+2), rare edge case (+1),
  duplicate non-representative (+1), first-of-template (+1).

Bands: HIGH (≥5), MEDIUM (≥2), else LOW (thresholds configurable).

## Sampling

1. Sort by (-risk, candidate_id); take highest-risk up to the audit rate.
2. Fill any remainder by seeded shuffle (`audit_seed`) so low-risk
   records can still be sampled.
3. `audit_rate: 0` disables sampling entirely.

Repeated runs return identical samples (tested).

## Results

`record_audit_result` stores PASS/FAIL/UNCLEAR + note on the item (no
timestamps, keeping outputs byte-stable). Unknown ids and PENDING
"results" are rejected loudly.

## Effect on selection

- FAIL → EXCLUDED with `AUDIT_FAIL`.
- Required (sampled) but undecided → `AUDIT_REQUIRED`, never GOLDEN.
- PASS → may proceed through remaining gates.
