# Funnel Generation Experiment

Status: proposed design only. This is a nonhistorical document: it does not
reinterpret an existing run, modify a frozen configuration, or authorize model
execution.

## Objective and Scope

Measure whether fixed, machine-generated execution feedback can recover
verifier-passing SQL for the complete current funnel catalog without changing
the task contracts or base prompt. The experiment is a bounded feasibility
study, not a claim of family accuracy, model superiority, or release quality.

The historical diagnostic found zero passing funnel candidates among 24
candidates (eight task instances with three attempts each), with 22 classified
model errors and two undetermined failures. Execution and visible result
mismatches motivated this retry treatment, but the same evidence does not
separate model error from prompt ambiguity or oracle error.

Sources: `docs/production/phase3-diagnostic-20261002.md` (lines 102-117 and
165-213), `docs/production/phase3-diagnostic-20261002.json`
(`decision_table`), and `docs/production/smoke-diagnosis-001.md`.

## Contract Population

`N = 8` deterministic task instances: one preregistered fixture seed for each
current funnel contract. The operator must assign and record the eight seeds
in a new experiment manifest before execution; seeds cannot be replaced after
seeing a result. The following table is the complete population, not a sampled
subset.

| Contract | Version | Required behavior and output |
| --- | ---: | --- |
| `sql.funnel.completion` | 2 | Per customer, find the longest ordered `view -> add_to_cart -> checkout -> purchase` prefix in `(event_time, event_id)` order. Sessions do not constrain the chain; return every customer with `customer_id`, `max_step_reached`, and `completed`. |
| `sql.funnel.checkout_paid_session` | 1 | Per 2025 acquisition channel, count started sessions and sessions with an ordered `product_view -> add_to_cart -> checkout_started` sequence plus a captured same-session payment at or before expiry. Include zero-conversion channels. |
| `sql.funnel.curriculum_gate_completion` | 1 | Per cohort, count distinct learners whose enrollment has every post-enrollment lesson passed and module completion keys in ascending stage order; include cohorts with zero completions. |
| `sql.funnel.kyc_document_approval` | 1 | Return 2025 applications that pass identity, have every country-required document's latest review approved, and receive an approved decision after those documents within 14 days of submission. |
| `sql.funnel.logistics_parcel_delivery` | 1 | Per depot, sum eligible parcel amounts whose ordered `accepted -> sorted -> dispatched -> delivered` chain completes, resolving equal times by `sequence`. |
| `sql.funnel.parcel_exception_recovery` | 1 | Per depot, count and sum delivery durations for 2025-accepted parcels whose latest exception is followed by recovery and delivery in `(scanned_at, scan_id)` order within 72 hours. |
| `sql.funnel.saas_activation_payment` | 1 | Per segment, sum eligible account amounts whose ordered `signup -> trial -> activation -> payment` chain completes, resolving equal times by `sequence`. |
| `sql.funnel.support_resolution_chain` | 1 | Return each ticket once when `opened -> assigned -> resolved` occurs as an ordered, non-adjacent subsequence in `(event_time, event_id)` order; repeats and intervening states do not reset progress. |

Contract sources: `templates/sql/funnel/completion_v2.yaml`,
`templates/sql/funnel/checkout_paid_session.yaml`,
`templates/sql/funnel/curriculum_gate_completion.yaml`,
`templates/sql/funnel/kyc_document_approval.yaml`,
`templates/sql/funnel/logistics_parcel_delivery.yaml`,
`templates/sql/funnel/parcel_exception_recovery.yaml`,
`templates/sql/funnel/saas_activation_payment.yaml`, and
`templates/sql/funnel/support_resolution_chain.yaml`. The catalog's contract
readiness status is recorded in `docs/production/phase3-diagnostic-20261002.md`.

## Sample Size and Cost Bound

The cap is 24 baseline-model calls: eight initial calls plus at most two
feedback retries for each of the eight contracts. This exactly matches the
historical 24-candidate funnel attempt count while covering every current
contract once. It is deliberately a feasibility-sized study; it has no
statistical power claim and produces descriptive rates with denominators of
eight contracts and at most 24 calls.

The baseline is a local model, so this design assumes no provider-billed
inference cost. It does not treat that as zero total cost: local hardware,
electricity, execution, verification, and storage inputs remain unknown until
measured. The operator must record wall-clock generation, sandbox execution,
verification, and retained-byte totals. Stop before a new call if the
preregistered 24-call or local resource limit is reached. No dollar, cost per
Golden, or production-cost claim is allowed from this experiment alone.

Cost sources: `docs/economics.md` and the local smoke proxy in
`docs/production/quality70-result-20261001.md` (lines 103-155).

## Frozen Treatments

All treatments use the exact selected template version, generated fixture,
instruction text, verifier, sandbox policy, and seed for their contract. They
must be content-hashed into a new manifest before the first call. No frozen
document, configuration, template, oracle, fixture, or historical run may be
changed for this experiment.

### A. Pinned Baseline

Make one SQL-only candidate request per contract with the existing local model
identity `alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest`
at revision `ollama-digest:a2d26ea0b96b7a40afd673158d5cf44de25eff07fc8abf835e2cde5444632bc4`.
Pin `prompt_version=sql-v2`, `temperature=0.3`, `top_p=0.9`, and
`max_tokens=2048`. A baseline candidate receives no prior SQL, execution error,
or verifier result difference.

The model revision and sampling values are sourced from
`docs/production/quality70-result-20261001.md` and
`configs/production/diverse_smoke_002.yaml`. The latter is a source reference,
not a config to modify or execute.

### B. Pinned Baseline Plus Feedback

For a baseline candidate that is not `PASS`, make at most two sequential retry
calls. Each retry keeps every baseline setting and the original task instruction
unchanged. The only added text is this fixed feedback envelope, mechanically
rendered from the immediately preceding candidate's recorded outcome:

```text
Previous candidate SQL:
<verbatim previous candidate SQL>

Verifier outcome: <normalized status>
Execution diagnostic: <verbatim sandbox message, or NONE>
Visible result difference: <normalized ordered expected/actual row differences, or NONE>

Return replacement DuckDB SQL only. Preserve the supplied task contract.
```

The envelope excludes oracle SQL, hidden fixtures, hidden-case outputs, manual
diagnoses, and any information from another contract. `Visible result difference`
is the verifier's ordered difference payload, truncated deterministically at
20 row differences and 8 KiB. For an execution failure it is `NONE`; for a
visible mismatch it carries the normalized mismatch payload. A hidden-only
mismatch has no feedback retry because its evidence is not safely exposable.
Stop retries immediately on `PASS`, after two retries, or on an infrastructure
failure. This is fixed execution/verifier feedback, not prompt tuning.

### C. Alternative Model, Pending User Selection

Do not select, download, or run an alternative model in this task. After the
user supplies an exact model ID, immutable revision/digest, and authorization,
the alternative-model arm repeats Treatments A and B on the same eight
contract/seed pairs with the same 24-call maximum. It must use a separate run
identity and cannot be pooled with the pinned baseline. Until those inputs are
provided, this arm is `PENDING_USER_SELECTION`.

## Predeclared Metrics and Decisions

Report every metric by contract and treatment, without dropping failed calls.

| Metric | Definition | Decision |
| --- | --- | --- |
| Baseline contract pass rate | Contracts with a `PASS` on their first call divided by 8. | Descriptive comparison with the historical 0/24 candidate result only; do not claim a causal improvement. |
| Feedback contract pass rate | Contracts with any `PASS` within their baseline call plus up to two feedback retries, divided by 8. | Advance to a separately authorized confirmation study only if at least 4/8 contracts pass and at least 2 baseline failures are rescued by feedback. Otherwise stop this treatment and diagnose artifacts without changing prompts. |
| Candidate pass rate | `PASS` calls divided by all completed calls, reported separately for initial and retry calls. | Context only; never substitute this for the contract pass rate. |
| Execution failure rate | Non-successful sandbox executions divided by submitted calls. | If greater than 25% overall, stop remaining calls and investigate runner/sandbox evidence before any rerun. |
| Visible-mismatch rescue rate | Feedback `PASS` calls divided by retries prompted by a visible result difference. | Descriptive; zero denominator is `NOT_APPLICABLE`. |
| Hidden-only mismatch count | Failed verification with no safe visible diagnostic. | No retry; retain as undetermined unless independent evidence later resolves it. |
| Resource use | Calls, elapsed seconds, sandbox seconds, verifier seconds, and retained bytes. | Stop at the 24-call cap or a preregistered local resource cap; report unknown cost inputs as unknown. |

The 4/8 and 2/8 thresholds are prospective operational gates, not estimates of
population performance. The alternative model is compared only after selection,
using the same metrics and thresholds; with eight paired contracts, report
paired outcomes and exact counts, not significance tests.

## Failure Handling

| Failure mode | Handling |
| --- | --- |
| Template, fixture, oracle, verifier, or sandbox integrity failure | Stop the affected experiment before model retry; label it `INFRASTRUCTURE_OR_CONTRACT_UNDETERMINED`. Do not alter the contract in place. |
| Model response missing, unparsable, or non-SQL | Record the raw response hash and parser status; it consumes the scheduled call. Retry only under Treatment B if the preceding call has an execution or visible result diagnostic. |
| SQL execution failure | Record the normalized sandbox message; permit the next fixed feedback retry if available. |
| Visible result mismatch | Record the ordered result difference; permit the next fixed feedback retry if available. |
| Hidden-only mismatch | Record the failure code without hidden values; no feedback retry. |
| Timeout, interruption, or transport failure | Charge the logical call, preserve partial receipts, and do not grant an unbounded replacement call. |
| All eight baseline calls fail | Complete only already-authorized feedback retries within the cap, publish no success claim, and stop after the preregistered report. |

No failure permits hand-written hints, contract edits, seed substitution, prompt
rewriting, temperature changes, model changes, or replay until a new design and
authorization exist.

## Logging and Artifact Paths

Before any call, create a new immutable experiment identity and write planning
artifacts only under:

```text
scratch/funnel-generation-experiment/<experiment-id>/
  manifest.json
  treatment-lock.json
  seeds.json
  source-hashes.json
  call-plan.jsonl
```

If separately authorized to execute, retain run evidence under the new path:

```text
runs/funnel-generation-experiment-<experiment-id>/
  manifest.json
  tasks/tasks.jsonl
  candidates/candidates.jsonl
  execution/triples.jsonl
  verification/verification.jsonl
  reports/funnel-experiment.json
```

Each call record must include experiment ID, contract ID/version, fixture seed
and task content hash, treatment and retry index, model ID/revision, sampling
parameters, base-prompt hash, feedback-envelope hash, candidate SQL hash,
response/parser status, execution status/message hash, verifier verdict,
visible-difference hash/count, hidden-case status without hidden contents,
timestamps, durations, and byte counts. Store raw artifacts only in the
experiment directory; report files must link to them by content hash.

Never reuse or rewrite a historical run directory. Artifact retention and
manifest requirements are sourced from `docs/production/artifact-retention.md`.

## Non-Tuning and Authorization Rules

This design fixes the base prompt and sampling parameters before the first
call. The feedback envelope is the only treatment variation, is deterministic,
and may not be edited after observing outcomes. No prompt tuning, few-shot
examples, hand-authored SQL, manual error interpretation, contract relaxation,
or adaptive model selection is allowed.

This document itself authorizes no generation, sandbox execution, download, or
model selection. A future execution requires an explicit user authorization,
a new configuration-bound run identity, exact source hashes, and the local
resource cap recorded before the first call.

## 2026-10-02 Arm Lock Update

This update supersedes the earlier eight-contract, 24-call proposal. The
experiment population is the seven `FULLY_VERIFIED` funnel contracts in
`manifests/phase3-contract-readiness.json`; `sql.funnel.completion` is excluded
because its mutation-applicability status is `no` (source: readiness manifest,
contract record `sql.funnel.completion`).

Each arm receives six initial candidates per contract, for 42 initial calls per
arm. Feedback arms permit at most two visible-diff retries for each failed
initial candidate, so their hard maximum is 126 calls per arm. No hidden,
property, or mutation evidence enters feedback. Feedback-assisted candidates
are tagged `feedback_assisted=true` in provenance.

| Arm | Model | Revision | Treatment |
| --- | --- | --- | --- |
| pinned-baseline | Huihui Devstral Small 2 24B | `ollama-digest:a2d26ea0b96b7a40afd673158d5cf44de25eff07fc8abf835e2cde5444632bc4` | six initial candidates only |
| pinned-feedback | Huihui Devstral Small 2 24B | same digest | six initial candidates; up to two visible-diff retries per failure |
| qwen-baseline | Qwen3-Coder 30B A3B | `ollama-digest:88cc37b8585d9ce9df3193b9624a7792c1fd9177c397e90c675b9370349aaad5` | six initial candidates only |
| qwen-feedback | Qwen3-Coder 30B A3B | same digest | six initial candidates; up to two visible-diff retries per failure |

The local tag inventory contains no non-abliterated Devstral-Small-2 24B exact
variant. `mistral-small:24b` is a different local model, not an eligible fifth
Devstral arm (source: `http://localhost:11434/api/tags`, observed 2026-10-02).

Before calls, record each arm's exact model digest, quantization, context size,
thinking-mode capability/state, temperature, top-p, task seed, prompt hash, and
feedback-envelope hash. Temperature and top-p are identical across all arms;
the only treatment variation is the fixed feedback envelope.

Predeclared outcomes: report per-contract initial and any-pass rates, contracts
with at least one `PASS`, and counts for parse, execution, visible-mismatch,
hidden-only, property, metamorphic, and mutation failures. A model capability
signal requires an arm to produce at least one verified pass for at least four
of seven contracts. A retry-help signal requires feedback to rescue at least
two contracts that had no baseline pass. A cross-model win requires Qwen to
exceed the pinned arm by at least two contracts with any verified pass on the
same seven contracts. If reference SQL or verifier integrity fails, classify the
affected contract as contract-oracle-undetermined; do not attribute it to a
model. Any prompt change after results must be logged with its reason and
creates a new arm identity.

## Pre-Call Amendment Audit

- Boundary rules: model-facing instructions and public requirements must be
  inspected per contract before calls. The checkout adversarial expectations are
  derived from its instruction's inclusive expiry and same-session rules; the
  remaining-contract provenance check is pending runner preflight.
- Paired retries: documented and locked above; retries reuse baseline calls.
- Candidate diversity: every log row records a nonzero temperature, deterministic
  seed, and raw/parsed SQL hash; reports count distinct SQL per contract/arm.
- Paused-run sanity: compare the pinned baseline's three overlapping contracts
  (`logistics_parcel_delivery`, `saas_activation_payment`,
  `support_resolution_chain`) to the paused-run failures before interpretation.
- Wall-clock and caps: each call records elapsed time; each arm stops at three
  hours and records a stop receipt.
- Directionality: all seven-contract thresholds are directional, with per-
  contract rates reported.
- Skip change: the prior run reported 117 skips while the latest run reported
  975 passes without a skip summary. Cause is UNKNOWN; no experiment conclusion
  depends on this difference.

## Instruction V3c, Pre-Call

Reason: audit finding: state-machine scope and ignored-event behavior were
previously only implied. V1 and V2 are retained in git/history; V3 introduced
an invalid `status=eligible` scope and V3b corrected status to funnel steps.

SaaS v3c: Return eligible completed SaaS activation-payment funnel value by
segment in 2025. For each entity, order records by occurred_at then sequence
ascending; a funnel completes when signup, trial, activation, and payment occur
in that order, with the first matching record advancing each step. Only rows
whose status is one of those four funnel steps in 2025 are in scope. For each
completed entity, use the amount on its matched payment event; sum those amounts
by segment. Include every segment with in-scope rows, returning zero total_amount
when none completes, and order segments ascending. Rows that do not match the
next expected step are ignored: they neither advance nor reset progress. Each
entity keeps one segment across its rows, so a completion counts toward that
entity's segment.

Logistics v3c uses the same mechanics with accepted, sorted, dispatched, and
delivered steps; scan, parcel, depot, and delivered-scan wording respectively.

## 2026-10-03 Authorized Scratch Execution Amendment

This amendment authorizes one scratch-only execution and supersedes conflicting
earlier path and population language. It does not authorize a production or
qualification run, change frozen sources, or modify the paused
`runs/premium-qualification-080` evidence.

The population is exactly the seven `funnel` contracts marked `FULLY_VERIFIED`
in `manifests/phase3-contract-readiness.json`. New artifacts are retained only
under `scratch/funnel-generation-experiment/<identity>/`; the runner must not
write to `runs/`, frozen configuration, templates, registry, gates, contracts,
or historical documentation.

Run four paired arms in this order: `pinned-baseline`, `pinned-feedback`,
`qwen-baseline`, `qwen-feedback`. The pinned pair uses
`alibilge/Huihui-Devstral-Small-2-24B-Instruct-2512-abliterated:latest` at
`ollama-digest:a2d26ea0b96b7a40afd673158d5cf44de25eff07fc8abf835e2cde5444632bc4`.
The Qwen pair uses `mdq100/Qwen3-Coder-30B-A3B-Instruct:30b` at
`ollama-digest:88cc37b8585d9ce9df3193b9624a7792c1fd9177c397e90c675b9370349aaad5`.
The observed local digest is checked before any call for that pair.

Each baseline makes six initial candidates per contract using `temperature=0.3`,
`top_p=0.9`, `max_tokens=2048`, and six distinct recorded sampling seeds.
Duplicate SQL fingerprints are recorded and are never replaced or collapsed.
Each feedback arm reuses its paired baseline candidate, execution, and
verification result; it makes no new initial calls. An eligible failed baseline
candidate receives at most two independently seeded replacements, both based on
that original candidate and its original initial-fixture outcome.

Before every feedback request, audit the boundary: the envelope may contain
only baseline SQL, normalized initial-fixture execution status/message, and the
normalized initial-fixture comparison difference (at most 20 rows and 8 KiB).
It must not contain oracle strategy, hidden/adversarial expected values or
outcomes, property, metamorphic, mutation, or retry evidence. The provenance
tag is `feedback_assisted=true`; initial records use `false`. This is visible
initial-fixture feedback only, not prompt tuning.

Each submitted call has a 180-second provider timeout and a recorded monotonic
wall-clock duration; the sandbox retains its independent 10-second timeout.
Each arm has a three-hour monotonic cap, checked before each call. A cap,
timeout, interruption, digest mismatch, or infrastructure fault stops that arm
without replacement. Report directional seven-contract rates: initial pass,
any-pass, feedback rescue against its paired baseline, and Qwen-minus-pinned
differences. No significance or quality-release claim is allowed.

The scratch report must also state the locked expected population (seven
contracts, six initial candidates per baseline arm, and retry eligibility only
after an initial execution failure or visible initial-fixture mismatch), then
derive completed, skipped, and unattempted counts from the call ledger. Every
skipped or unattempted call must have a cause, including a paired initial pass,
hidden/property/metamorphic/mutation-only failure, prior retry pass, arm cap,
timeout, interruption, digest mismatch, or infrastructure stop. These counts
are operational accounting only and must not be filled from qualification or
historical-run evidence.

Before model calls, record a read-only paused-run sanity check for
`sql.funnel.logistics_parcel_delivery`, `sql.funnel.saas_activation_payment`,
and `sql.funnel.support_resolution_chain`. Skip/drop investigation is read-only:
it cannot edit, delete, rerun, or reinterpret the paused run.
