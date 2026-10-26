# Stage 2 receipt schema v2 — validation contract

Status: validator slice implemented, **Stage 2 still active and incomplete**.
No v9 producer profiles have been generated or independently cold-verified.
This is a new document; prior evidence and receipts remain history.

## Authority and API

The existing APIs remain `receipt(root, reference, contract, version, category)`
and `qualify(root, record)`. A reference is a root-relative `path` plus lowercase
SHA-256. Absolute/escaping paths, missing files and stale hashes deny admission.

`receipt` validates **one category**, not whole-contract eligibility. Its success
string remains `fresh executed evidence` for caller compatibility. `qualify`
requires all seven validated categories, structural prerequisites, supported
independence, public identity and effective authority. The independent counter
calls `qualify`; it rejects reported labels that disagree with recomputation.

Missing/non-v2 schemas are explicitly denied as:
`stale or unsupported legacy evidence`. Do not edit historical receipts to add
v2 labels. Create new retained evidence only after producer/source stability.

Public identity is the exact loaded template/version and oracle entry, not a
caller catalog. The retained base `TaskInstance` must equal canonical
`generate_task(template, seed, generation_metadata.config)` output. Its public
requirements compare as type-sensitive canonical JSON. Duplicate schema table
names deny before dictionary construction. Public instruction binding uses
`generate_fixture_tables(template, seed)`'s actual sorted ensured edges; it does
not reuse the caller's edge list or assume all template cases always inject.
The ledger separately retains the actual declared edge-case list.

Quarantine authority is fixed at
`root/manifests/package-a-contract-quarantine.json`, version 1. Missing, malformed
or duplicate entries deny. Matching is exact contract/version. Caller `None`,
quarantine objects and status labels cannot erase or invent authoritative state.

Effective evidence authority is the existing read-only journal/materializer at
`root/scratch/funnel_experiment/evidence/events.jsonl` and `index.json`. The index
must equal materialization of the journal. Each admitted category needs its own
ACTIVE, nonsuperseded event, bound to evidence ID, exact contract/version,
category, artifact path/hash and producer script. Use the existing event fields
required by `scripts/package_a_evidence.py` and add `category`. No journal/index
writes were made in this slice. Historical INFORMATIONAL aggregate events do
not establish active per-category eligibility.

## Envelope

The executable schema is `verification/receipt_models.py`; extra fields are
forbidden. `ReceiptV2` requires:

- `schema_version: 2`, evidence ID, producer root-relative Python path, ISO
  creation timestamp, exact contract ID/version and one of the seven categories.
- `task: ArtifactRef` to the canonical base task JSON (schema serialized by alias).
- Current `oracle_version`, current `comparison_version`, and
  `behavior_map_sha256` from the current public declaration ledger.
- `source_hashes`, positive integer `checks_run`, integer-zero
  `execution_failures`, empty `unresolved_findings`, exact `metrics`, and `details`.

`status` is deliberately **not** a v2 receipt field; journal authority supplies
effective state. Source locks currently require a conservative complete `src`
Python closure, all loaded-template YAML/YML files, the frozen rubric and the
pure journal helper. The producer Python file must also be locked. Every supplied
lock is rehashed beneath root. This core closure is intentionally broad, not a
completed narrow producer import/input closure. The next producer must add every
consumed test/helper, corpus, private JSON/Python, relation JSON, reference SQL and
configuration input. Hash-bound detail artifacts are additionally dereferenced.

Thresholds are read from the source-locked frozen rubric, not receipt flags:
four distinct fixtures, seeds `[1,43,94001]`, two discriminating relations, three
distinct valid semantic mutants, twenty wrong challenges, three correct
alternatives, 300 random cases per seed and twenty observed behavior cases per
seed. Nonpassing outcomes are rejected, never counted as semantic evidence.

## Shared retained witnesses

`FixtureWitness` contains a tables JSON reference, canonical database-content
`fingerprint`, full typed `ExpectedResult`, origin (`original`, `seed`, `targeted`)
and optional seed. Table/column shape, multiplicity and declared DB domain are
checked. The fingerprint and current versioned oracle result are recomputed.

`SQLWitness` contains references to SQL text, full `CandidateSolution` JSON and
full `ExecutionResult` JSON, a fixture witness, full `ComparisonResult`, and
outcome `MATCH` or `KILLED_WRONG_ANSWER`. Candidate/task/SQL binding, successful
terminal status, derived execution ID, time ordering, resource/row consistency,
truncation, current DuckDB version and typed output are checked. A reused execution
ID cannot bind different SQL/fixture/result records. A reference to the same run
does not invent another execution.

SQL is replayed on materialized rows after disabling external access, with one
thread, 128 MB, a five-second interrupt and a 100,000-row cap. Invalid SQL,
policy failures, replay errors and retained-output disagreements deny. Full
comparison is recomputed with the authoritative default policy; receipt-supplied
tolerances cannot change acceptance.

This provides binding, consistency and an actual local replay, **not cryptographic
attestation of a historical producer/container run**. Positive SQL tests explicitly
retain real local DuckDB executions, not sandbox or provider claims. The next
producer must retain its genuine executions and align engine versions; it must
not fabricate result models to label unexecuted work successful.

## Category details and metrics

| Category | Details | Recomputed metrics / checks |
| --- | --- | --- |
| `rules` | Complete unique `RuleWitness` list matching every public ledger ID, kind and declaration. Disposition is `SEMANTIC_DISCRIMINATOR`, `DOMAIN_REJECTION` or `BLOCKED`. Semantic proofs retain same-fixture correct/wrong executions; domains retain invalid tables and exact rejection. | Incomplete, invented, waived or BLOCKED obligations deny. **No complete rule receipt can currently establish admission:** the opaque instruction ledger is not granular behavior proof, and unsupported domain dispositions stay blocked. |
| `named_tests` | Actual XML report reference, exact node-to-terminal-outcome dictionary, command and integer-zero exit code. Each testcase needs properties `node_id`, `contract_id`, `contract_version`. | Source AST file/class/function identities, XML class/name, duplicate properties, terminal suite counts and outcomes are checked. All attributed nodes must match; failed/error nodes deny. `passed`, `failed`; checks = attributed passed nodes. |
| `fixture_diversity` | At least four distinct `FixtureWitness` records, including original and three seeds. | Original content must match base task. Seed contents must equal `diverse_hidden_tables(task, seed, variant)` where variant is seed's position in the frozen seed list plus one. Nonempty, nonconstant outputs required. `distinct_contents`, `seed_cases`; checks = distinct retained fixture records. |
| `mutation` | Full public semantic `required_rules`, at least three `MutationWitness` records containing rule IDs and paired correct/wrong SQL witnesses. | Distinct wrong SQL and complete public semantic coverage required. Domain IDs cannot count as semantic rules. Opaque instruction attribution remains blocked. `valid_non_equivalent`, `semantic_kills`, `rule_coverage`; checks = distinct retained execution IDs. |
| `challenge` | At least twenty wrong SQL witnesses and three distinct correct SQL alternatives. Retain each correct alternative on every distinct wrong-query fixture. | Duplicate wrong queries or duplicate correct SQL/fixture pairs do not count. `witnessed_wrong`, `qualified_correct`, `false_acceptances:0`, `false_rejections:0`; checks = distinct execution IDs. |
| `relations` | Two unique identified transforms, version 2, exact precondition, correct before/after and same-wrong-query before/after SQL witnesses. | Reuse `contract_relation_tables`. Correct before/after must match oracle; wrong before must match and transformed wrong after must disagree. Fixtures and transform are recomputed. `executed`, `discriminating`, `failed:0`; checks = distinct execution IDs. |
| `fuzz` | Versioned observation policy, exactly 900 `FuzzCase` records across frozen seeds/indices, actual observed behaviors, three stable distinct alternative SQL witnesses per case, and per-seed observed counts. | Recompute deterministic source-bound fixture recipe, canonical content, observations and outcomes. Duplicate cases/labels, fake counts, unsupported policy, input substitution, alternative divergence or incomplete coverage deny. `valid_random_cases:900`, `observed_coverage_pass:true`, `divergences:0`; checks = distinct execution IDs (normally 2700). |

Observation policies currently support only SaaS v2 and scrap v1. Their recipes
and classifiers are source-bound in `receipt_observations.py`, with parity tests
against existing producer helpers. The observation-inventory arithmetic helper
alone is not fuzz execution qualification: actual fixtures and SQL outcomes must
also validate. No full executed 900-case receipt positive was produced here.

Every metric dictionary and check count must equal recomputation exactly. Summary
booleans, plausible counts, output samples, execution IDs alone and source presence
do not substitute for the corresponding retained details.

## Exact next producer/authority work

1. Cold-review these validators and schema, especially local replay/provenance,
   source-closure breadth, relation assumptions and typed domain dispositions.
2. Finish explicit granular public instruction/requirement behaviors and legal
   domain proofs before claiming complete rules or mutation coverage. Do not
   simply distribute a generic wrong SQL result across unrelated public rule IDs.
3. Update rejudge and producer helpers to retain complete typed rows, comparisons,
   candidate/execution artifacts, fixture content and exact versions. Current
   producer remains unchanged and emits incompatible lossy legacy summaries.
4. Capture XML node/contract properties during genuine test execution. Attribute
   checks by contract/category; retain all alternative-by-fixture checks.
5. Close producer dependencies over real imported/executed inputs and retain
   deterministic 900-case fuzz details with actual alternative runs. Enumerate
   latest public templates; unsupported contracts remain blocked.
6. Only after source is stable and producer positives have passed independent cold
   review, create new v9 artifacts and append legitimate per-category events if
   needed. Never rewrite history or claim qualification for the unresolved 39+16.

Stage 1 phase10r3 certification remains historical evidence for its exact original
snapshot. No full regression or Stage 3+ work is authorized by this document.
