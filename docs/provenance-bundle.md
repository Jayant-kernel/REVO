# Provenance Bundle

Status: **implemented** (Phase 6). Self-describing, deterministic
audit/reproduction bundle for one Golden dataset snapshot.

## Layout (`provenance_bundle/`)

```text
manifest.json            RunManifest (auditable run record)
reproduction.json        ReproductionManifest (what replay needs)
snapshot.json            DatasetSnapshot (content-defined membership)
nodes.jsonl              ProvenanceNode records (node_id order)
edges.jsonl              ProvenanceEdge records (edge_id order)
activities.jsonl         ProvenanceActivity records (run_id order)
artifacts.jsonl          ArtifactRef records (artifact_id order)
golden_records.jsonl     GoldenRecord dicts (candidate_id order)
reproducibility.json     ReproducibilityReport per Golden record
completeness.json        ProvenanceCompletenessReport array (one document)
```

## Determinism rules (§37)

Stable record ordering (above), canonical key ordering, UTF-8 with LF
newlines, deterministic numerics, no machine-specific absolute paths
(artifact locators are relative logical paths), and no volatile fields
in identity-bearing positions. Rewriting a bundle from its own
read-back yields byte-identical files (tested).

## Reading a bundle

`read_bundle(dir)` validates presence of all ten files and parses them
(`FileNotFoundError` lists what's missing). Consumers re-validate with
`ProvenanceNode.model_validate` etc. before trusting content.

## Manifest comparison (§47–48)

`compare_reproduction(expected, actual)` diffs two reproduction
manifests field by field into `ReproducibilityDiff` with spec categories
(`SOURCE_CHANGED`, `DEPENDENCY_CHANGED`, `MODEL_CHANGED`,
`PROMPT_CHANGED`, `GENERATION_CONFIG_CHANGED`, `SANDBOX_IMAGE_CHANGED`,
`SANDBOX_POLICY_CHANGED`, `VERIFICATION_CONFIG_CHANGED`,
`QUALITY_CONFIG_CHANGED`, `ARTIFACT_CHANGED`,
`DATASET_MEMBERSHIP_CHANGED`). Identical manifests diff to VERIFIED with
no entries; any drift is CONDITIONAL with structured entries. Operational
only-fields (extra timestamps, display names) do not affect the outcome.

## Security considerations

- Bundles reference artifacts; they do not smuggle blobs or secrets.
- Secret scrubbing applies at node construction; environment snapshots
  carry names, never values (asserted by test with sentinel secrets).
- Only repository-scoped or caller-supplied paths are inspected; the
  layer never trawls user files.
