# Phase 5 — Dataset Quality & Audit

Status: **implemented**. Sits strictly downstream of Phase 4: consumes
`(TaskInstance, CandidateSolution, ExecutionResult, VerificationResult)`
bundles and decides which verified records belong in the Golden Dataset.
Never regenerates candidates, never executes SQL, never re-judges
correctness. No LLM judge anywhere.

## Architecture

```text
VerifiedRecord bundles
        │ record_quality (per-record evidence: task + verification restated)
        ▼
duplicate_detection (exact/structural/semantic groups, hash-indexed)
        │ diversity / coverage / difficulty (distributions, fixed taxonomies)
        ▼
contamination (role overlap, template leakage, known-source registry)
        │ audit sampling (deterministic risk-based)
        ▼
golden selection (hard gates, then dedup + quotas, deterministic)
        │ health report (multi-dimensional, no magic score)
        ▼
export (golden/excluded/inconclusive/audit_required JSONL + health JSON)
```

Modules mirror the pipeline: `models`, `config`, `record_quality`,
`task_quality`, `duplicate_detection`, `diversity`, `coverage`,
`difficulty`, `contamination`, `audit`, `golden`, `aggregation`,
`health`, `export`, `api`, `errors`. Public surface is `quality.api`;
`factory quality ...` wraps it thinly.

## Key decisions (see ADR-008)
- Verification PASS is necessary, never sufficient.
- Evidence over scores; every exclusion keeps machine-readable reasons.
- Duplicates recorded with deterministic representatives, never deleted.
- Mutation NOT_APPLICABLE is not a perfect score (gates require SCORED
  evidence unless the suite genuinely cannot apply).
- Exported artifacts are byte-identical across runs: volatile telemetry
  (verification timestamps, oracle runtime, performance duration) is
  projected out of export blobs; decisions carry no timestamps.
- Difficulty is DECLARED unless solve-rate data exists (it does not for
  single-attempt records — stated explicitly, never manufactured).

## Configuration

`QualityConfig` (`configs/quality_example.yaml`): mutation threshold
(default 0.9), strong-verification requirement, family quotas/share caps,
audit rate/seed/thresholds/weights, contamination hard/soft rules,
known-source hashes, selection seed. All policy lives here, not in code.

## CLI

```bash
factory quality record --input records.jsonl [--output qualities.json]
factory quality dataset --input records.jsonl [--config q.yaml] [--out-dir out/]
factory quality duplicates --input records.jsonl
factory quality coverage --input records.jsonl
factory quality health --input records.jsonl
factory quality golden --input records.jsonl [--output golden.txt]
factory quality audit --input records.jsonl [--output sample.json]
factory quality audit --input records.jsonl --record-id ID --result PASS --output sample.json
```

Records file: JSONL of `{task, candidate, execution, verification, role?}`.

## Reproducibility

Same records + config + versions → identical groups, metrics, samples,
decisions, and export bytes (tested: full pipeline twice + byte-identical
exports). Sampling uses explicit seeds; sorting breaks all ties by
candidate_id.

## Testing

`tests/quality_dataset.py` builds a 13-record adversarial fixture (golden
material, invalid task, FAIL, INCONCLUSIVE, exact/structural/semantic
dups, rare family, thin edges, survivor-PASS, TRAIN/PRIVATE_EVAL
contamination pair). Suites cover every §25 bullet plus invariants
(determinism, monotonicity, FAIL/INCONCLUSIVE/contamination safety,
duplicate consistency, evidence preservation).

## Audit remediation (zero-applicable mutants, quarantine)

- A record whose mutation suite is NOT_APPLICABLE (or applicable count
  is zero) keeps that state distinctly: it is never scored, never
  assigned 1.0, and cannot become Golden without an explicit persisted
  justification (`justifications` map into `select_golden` /
  `analyze_dataset`, or `RecordQuality.mutation_justification`).
  Missing justification yields EXCLUDED with reason
  `MUTATION_JUSTIFICATION_REQUIRED`. Threshold 0.9 unchanged.
- Deterministic quarantine (`quality.quarantine`): versioned entries
  demote records before dedup/quotas with reason QUARANTINED.
  Historical artifacts are never modified; the pilot-001 UNKNOWN-strength
  outlier is quarantined by entry, not by edit.

## Limitations

- Semantic similarity is fingerprint-based (family+schema+operators),
  not embedding-based; near-paraphrase tasks outside fingerprints group
  separately by design.
- Empirical difficulty needs multi-attempt data (not yet collected).
- Audit is sampling + JSONL results; no UI.
- Contamination covers registered/structural overlap, not the internet.
