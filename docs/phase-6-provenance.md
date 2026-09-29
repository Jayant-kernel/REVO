# Phase 6 — Provenance & Reproducibility

Status: **implemented**. Records where every Golden artifact came from,
what produced it, and what would be needed to reproduce it — without
re-running generation, execution, verification, or quality logic, and
without redefining their semantics. No LLM judge anywhere.

## Architecture

```text
VerifiedRecord + RecordQuality + GoldenRecord + AuditSample + configs
        │ lineage.build_provenance (deterministic graph)
        ▼
nodes (content ids) + edges (lineage relations) + activities (runs)
        │ dataset_snapshot (content-defined membership)
        ▼
manifests (run + reproduction) + source/environment/model snapshots
        │ completeness + reproducibility assessment
        ▼
export (provenance_bundle/ — nine files, canonical bytes)
```

Modules mirror the pipeline: `models`, `errors`, `canonical`,
`hashing`, `nodes`, `edges`, `activities`, `config`, `environment`,
`source`, `store`, `artifacts`, `manifests`, `lineage`,
`reproducibility`, `dataset_snapshot`, `completeness`, `export`, `api`.
Public surface is `provenance.api`; `factory provenance ...` wraps it thinly.

## Key decisions (see ADR-009)

- Traceability is not reproducibility: the graph records origin; layer
  assessments report what replay each layer actually supports.
- Content identities (`sha256:<hex>`) cover identity-bearing payloads
  only — run ids, timestamps, and durations are operational metadata and
  are excluded by construction (not stripped silently: payload schemas
  document the boundary).
- Model nondeterminism is represented, never wished away: generation is
  CONDITIONAL at best (origin reconstructable, regeneration unguaranteed).
- Execution reproducibility caps at CONDITIONAL without a fully pinned
  environment, and NOT_VERIFIED without an image digest.
- Secrets never enter provenance artifacts (scrubbed structurally, with a
  redaction count; environment captures names, never values).
- Corrections are new records (SUPERSEDES), never rewrites.

## Configuration

`ProvenanceConfig` (`configs/provenance_example.yaml`): raw-artifact
emission, inline byte cap, source scope. Layer configs are snapshotted
from the actual Phase 2/3/4/5 configurations in use — never bare paths.

## CLI

```bash
factory provenance record --records R.jsonl --qualities Q.jsonl --golden G.jsonl \
  [--audit A.json] [--quality-config q.yaml] [--verification-config v.yaml] \
  --name my-set --out bundle/
factory provenance run [--output run.json]
factory provenance lineage --bundle bundle/ --golden-record <node-id>
factory provenance validate --bundle bundle/
factory provenance reproducibility --bundle bundle/ [--golden-record <node-id>]
factory provenance snapshot --golden G.jsonl [--quality-config q.yaml] --name my-set
factory provenance export --bundle bundle/ --out copy/
```

## Reproducibility

Same records + configs + versions → identical content ids, artifact
hashes, snapshot id, graph topology, and manifest identity (tested by
byte-comparing two full pipeline runs; operational run ids and
timestamps may differ but never leak into identities).

## Testing

`tests/provenance_fixtures.py` builds a 13-record adversarial fixture
(golden/excluded/inconclusive/audit results) through the real Phase 1–5
stack. Suites cover every §45 bullet: canonicalization, hashing,
artifacts, graph validity/immutability, snapshots, model honesty,
task/candidate/execution/verification/quality provenance, dataset
snapshots, layer assessments, secrets, and the full §46 chain.

## Limitations

- Execution replay needs the pinned image + daemon + fixture; the report
  says CONDITIONAL, never VERIFIED, without full environment pins.
- Model regeneration is not guaranteed for nondeterministic stacks.
- Source fingerprints degrade gracefully (UNKNOWN + dirty flag) outside git.
- The store is local JSONL (no server, no cloud) by MVP design.
