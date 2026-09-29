# Licensing / Provenance Policy — Verified SQL Data Factory

## Policy

> We use only models, datasets, code, and other source materials whose
> applicable licenses and terms permit the intended generation,
> transformation, verification, and commercial distribution workflow.

## What this means in practice

- Every model, dataset, code dependency, and source artifact must eventually
  have an explicit license/provenance record (`LicenseRecord` in
  `docs/data-model.md`; provenance metadata in `docs/golden-record.md`).
- License review happens **before** integration, not after:
  model licenses are researched and recorded as part of the Generation phase
  (Phase 2), before any weights are downloaded or served.
- Dataset exports (Phase 7) require a complete license chain; anything with
  unclear terms is excluded from commercial artifacts.

## Explicit non-claim

> "Open-weight" does NOT automatically mean "commercially safe."

Open-weight models carry distinct licenses and acceptable-use terms that must
be checked individually (redistribution terms, attribution, share-alike or
behavioral-use clauses, output-ownership questions). No blanket safety claim
is made here.

## Initial models (to be researched in Phase 2, not used in Phase 0)

- `Qwen3-Coder-30B-A3B-Instruct`
- `Devstral-Small-2-24B-Instruct-2512`
- `Qwen3-30B-A3B-Thinking-2507` (optional reasoning/teacher)

No model is downloaded, served, or integrated in Phase 0. License research
and recording is a Phase 2 entry requirement.
