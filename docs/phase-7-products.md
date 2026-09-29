# Phase 7 — Data Products (as-built)

Status: **implemented** (`verified_data_factory.products`).

## Authority boundaries

- Phase 4 owns correctness, Phase 5 owns Golden qualification, Phase 6
  owns provenance. Phase 7 owns packaging, release identity, schema
  versioning, and product validation — nothing else.
- Phase 7 never re-runs SQL, regenerates candidates, re-verifies,
  recalculates mutation scores, redefines Golden selection, mutates the
  snapshot, or adds an LLM judge.

## Pipeline

```
DatasetSnapshot (Phase 6, immutable input)
  → visibility filtering (code-enforced, §40)
  → deterministic group-aware splitting (§14–§17)
  → profiled transformation to Training/Evaluation/Benchmark records
  → sharded JSONL/Parquet serialization
  → manifest + SHA256SUMS + dataset card + preview + metrics
  → self-validation (build fails unless VALID)
```

## Product model

`DatasetSnapshot + ProductConfig + SchemaVersion + SplitPolicy +
PackagingFormat → DataProductRelease`. One snapshot yields many
products; each release carries a content-defined `release_id`.

See `docs/product-model.md`.

## Profiles and visibility

- `TRAIN`: input + target, provenance by reference.
- `PUBLIC_EVAL`: question + schema, targets withheld.
- `PRIVATE_EVAL`: internal only, may carry targets + verification summaries.
- `BENCHMARK`: stable `benchmark_item_id` per item.
- `SAMPLE`: capped public-safe preview of the training shape.
- A `PUBLIC` release rejects `PRIVATE_EVAL` roles, hard contamination
  flags, and `INTERNAL_ONLY` records by code — never by operator discipline.

## Splits

Deterministic function of (record identity, split policy): SHA-256 over
`seed + group key + candidate id`. Groups — never rows — are assigned,
so duplicate/semantic groups cannot straddle splits. No random sampling
without an explicit seed.

See `docs/splits.md`.

## Release layout

See `docs/release-format.md`. Validation (`validate_release`) re-checks
manifest integrity, checksums, schema conformance, split isolation,
provenance references, and visibility. Errors fail; warnings inform.

## Consuming

See `docs/consuming-products.md`. The only supported entry point is
`products.load_release` (strict: schema + checksum + visibility
re-checked on every load).

## CLI

- `factory product build --golden golden.jsonl --quality qualities.json
  --snapshot snapshot.json --config product.yaml --out-dir release/`
- `factory product validate --release-dir release/`
- `factory product diff --a A --b B`
- `factory product load --release-dir release/ [--show-one]`
- `factory product splits --golden ... --quality ... [--seed N]`

## Non-goals (enforced)

Marketplace, payments, customer systems, model training, new SQL
dialects, LLM judges, snapshot mutation. Phase 8 owns commercialization.
