# Provenance Model

Status: **implemented** (Phase 6). Node/edge vocabulary, content
identity, and canonicalization contract for all lineage artifacts.

## Node types

`TASK_TEMPLATE`, `TASK_INSTANCE`, `GENERATION_RUN`, `CANDIDATE_SOLUTION`,
`EXECUTION_RUN`, `EXECUTION_RESULT`, `VERIFICATION_RUN`,
`VERIFICATION_RESULT`, `QUALITY_RUN`, `RECORD_QUALITY`, `AUDIT_SAMPLE`,
`AUDIT_RESULT`, `GOLDEN_SELECTION`, `GOLDEN_RECORD`, `DATASET_SNAPSHOT`,
`CONFIGURATION`, `SOURCE_SNAPSHOT`, `ENVIRONMENT_SNAPSHOT`,
`MODEL_SNAPSHOT`, `ARTIFACT`.

Entities (things that exist) vs activities (things that ran) are kept
distinct: `ProvenanceNode` carries content identity; `ProvenanceActivity`
carries operational run metadata (unique run ids, timestamps) and is
never part of a content hash.

## Edge types

`DERIVED_FROM`, `GENERATED_BY`, `EXECUTED_BY`, `VERIFIED_BY`,
`QUALIFIED_BY`, `AUDITED_BY`, `SELECTED_BY`, `INCLUDED_IN`,
`EXPORTED_AS`, `USES_CONFIGURATION`, `USES_ENVIRONMENT`, `USES_MODEL`,
`USES_ARTIFACT`, `SUPERSEDES`.

Read directionally, e.g. `CANDIDATE_SOLUTION —EXECUTED_BY→ EXECUTION_RUN`
(the candidate was executed by that run). The one deliberate asymmetry:
`TASK_INSTANCE —DERIVED_FROM→ TASK_TEMPLATE` (instance derived from
template); lineage tracing therefore follows incoming edges plus
outgoing `DERIVED_FROM` edges to reach origins. Allowed triples are
enumerated in `edges.py`; anything else is rejected.

## Content identity

`sha256:<hex>` over `canonical_json({"type", "schema_version",
"payload"})` — domain separation across node types is structural, not
conventional. Every persisted provenance structure carries
`schema_version`. Python's `hash()`, memory addresses, and timestamps
never participate.

Volatile run identifiers (`execution_id` embeds a timestamp;
`verification_id` derives from it) are deliberately EXCLUDED from
hashed payloads. They remain retrievable in raw artifacts and
activities — traceability without poisoning determinism.

## Canonicalization

One mechanism (`provenance.canonical`), shared by hashing, manifests,
IDs, fingerprints, and snapshots:

- mappings sorted by key; lists ordered; tuples → lists;
- sets → sorted tagged `$set` (never collide with `[]`);
- strings NFC + UTF-8 (`ensure_ascii=False`);
- booleans/nulls literal; integers exact; floats finite-only, `repr`;
- `Decimal` → `{"$decimal": str}` (never collides with float);
- datetimes → `{"$datetime": iso}`; bytes → `{"$bytes": hex}`;
- enums → `.value`; Pydantic → `model_dump(mode="json")`;
- anything else raises `CanonicalizationError` (no silent `repr()`).

## Artifact hashing

`ArtifactRef` = id + type + content hash + size + media type + logical
name + relative locator + producing run (+ optional compression,
encoding, schema version). Files stream in 64 KiB chunks; same content
always resolves to the same hash regardless of location. References
point at existing artifacts; the store never ingests blobs.

## Model supply-chain records

`provenance.supply_chain.ModelSupplyChain` records evidenced facts
about a generating checkpoint (name, revision, source, claimed license
only with its source reference, format, quantization, modifications
including ablation flags, parent lineage only if evidenced) with
statuses UNVERIFIED / DOCUMENTED / REVIEW_REQUIRED / APPROVED /
BLOCKED. Nothing is inferred: unevidenced fields stay empty and the
status stays unresolved. `commercial_clearance_decision` permits a
commercially-cleared label only for APPROVED records with a recorded
sign-off. Historical model snapshots are never modified; a replacement
checkpoint naturally yields new snapshot, configuration, and run
identities by content addressing.

## Secret safety

`scrub_secrets` drops secret-valued keys (api keys, tokens, passwords,
bearers, credentials, private keys…) at any depth and reports a
redaction count. Environment snapshots record safe variable *names*
only. Tests assert sentinel secrets never appear in any serialization.
