# Product model — snapshot → release

## Identity

```
DatasetSnapshot + ProductConfig + SchemaVersion + SplitPolicy + PackagingFormat
  → DataProductRelease
```

Every input is content-addressed:

- `dataset_snapshot_id` (Phase 6, immutable Golden membership).
- `product_config_id` = `content_id("PRODUCT_CONFIG", "1.0", config payload)`.
- `split_policy_id` = `content_id("SPLIT_POLICY", "1.0", policy payload)`.
- `release_id` = `content_id("DATA_PRODUCT_RELEASE", "1.0", payload)`
  covering snapshot id, config id, policy id, schema name/version,
  transformation version, output format, split counts, and sorted shard
  hashes. Timestamps, paths, and run ids never enter any identity, so
  rebuilding identical inputs yields an identical `release_id`.

## Canonical schema

`verified-data-factory/sql/1.0`, DuckDB-only. Every GoldenRecord field
is explicitly classified (`MODEL_INPUT`, `MODEL_TARGET`, `METADATA`,
`PROVENANCE`, `INTERNAL_ONLY`) in `products.schemas.FIELD_CLASSIFICATION`,
so internal data cannot leak silently. The schema is never extended
without a version bump; loaders reject unsupported major versions with
an explicit error (§38).

## Record shapes

- **TrainingRecord**: `task_id, instruction, schema, sql` plus
  `template_id, template_version, task_family, difficulty, dialect`,
  with `golden_record_id` and `dataset_snapshot_id` (provenance by
  reference — full lineage stays in Phase 6).
- **EvaluationRecord**: same, but `sql` is optional and withheld unless
  the profile allows targets; carries its `split`.
- **BenchmarkRecord**: EvaluationRecord plus a stable
  `benchmark_item_id` (`bench-{index:06d}-{candidate_id}`).

Malformed records fail validation; they are never repaired.

## Release counts

`manifest.split_counts` is the full deterministic split plan (all four
splits); `manifest.record_count` is what the release actually ships
(the product-type split only). Shard hashes already fix the shipped
content, so the release id is unaffected by this derived count.
