# Release format

A release is a directory:

```
release/
  manifest.json      authoritative descriptor (canonical JSON)
  SHA256SUMS         BSD-style `SHA256 (<relpath>) = <hex>` lines
  data/
    shard-00000.jsonl | .parquet
    ...
  metrics.json       release metrics (referenced from Phase 5, not recomputed)
  dataset_card.md    factual card rendered from actual metrics
  preview.json       first N records (pretty JSON; N = preview_size, 0 = skip)
  validation.json    last `validate_release` report
```

## Serialization

- **JSONL** (canonical): one UTF-8 line per record, stable key order,
  `\n` terminators. The canonical interchange format.
- **Parquet**: mirrors JSONL column-for-column with JSON scalar types
  preserved (int → int64, float → float64, bool → bool, else string;
  nulls kept). Same logical records, same schema version.
- Records are written in candidate-id order inside
  deterministically named shards (`shard-{index:05d}`); `shard_size`
  controls rows per shard (0 = single shard). Empty products still ship
  one (empty) shard so consumers see a uniform layout.

## Manifest

`manifest.json` carries product name/type/visibility, `release_id`,
snapshot/config/policy/schema/transformation ids and versions, shipped
`record_count`, full `split_counts` plan, per-shard hashes and sizes,
file entries with media types, `created_at` (informational only —
excluded from identity), and factory/provenance versions.

## Validation

`validate_release` checks manifest presence/parse, file presence/size/
SHA-256, SHA256SUMS consistency, per-record schema conformance under
the product profile (eval products must *not* carry targets),
shard disjointness, shipped-count agreement, snapshot-id agreement,
PUBLIC visibility (no target leaks), and card/preview presence
(warnings only). Errors → `INVALID`; warnings never fail. The report is
persisted as `validation.json`.

## Remediation gates and audit commands

Optional audit inputs activate further machine-readable gates on
`validate` (absent inputs skip without failing): `--quarantine`
rejects shipped quarantined rows (`release.quarantine`); `--quality`
(+ `--justifications`) re-checks per-row mutation evidence
(`release.mutation_evidence`, `release.mutation_threshold`,
`release.contamination`); `--supply-chain` enforces commercial
clearance (`release.commercial_clearance`). `build` accepts
`--quarantine` and refuses quarantined snapshot members outright.

`factory product manifest` exports a deterministic per-row provenance
manifest (customer view drops internal run ids); `factory product
census` regenerates the corpus census and optionally the Markdown
audit report from stored artifacts.

## Diffing

`diff_releases(A, B)` compares manifests plus per-record canonical
hashes: added/removed/changed record ids and split/schema/config/
snapshot/format change flags.
