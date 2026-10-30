# Runtime qualification v2 ledger

## v34 — published qual20; source-bound final audit passed

Primary current handoff: v34 supersedes the stopped v33 outcome below, not its
historical bytes. New producer `NEW v2/qualification-v34.py` froze 539 source
inputs once; v32/v33 producers, receipts and old source hashes were not edited.
No core/scripts/tests/templates edits were made by this runtime task. The new
controller uses the immutable v33 controller as an explicitly hashed input.

Before collection, actual `ArtifactWriter.rules()` -> serialized receipt ->
independent public `readiness.receipt()` succeeded. Focused existing regression:

```text
python -m pytest -q tests/test_renewal_probe_roundtrip.py
2 passed in 18.35s
```

Executed controller commands: `freeze`, `preflight`, `advance --seconds 900`,
three bounded `advance --seconds 1800` invocations, a final
`advance --seconds 900`, then `audit`. All completed without a semantic failure.
Each category additionally passed independent public JSON receipt replay before
its checkpoint. Renewal reused unchanged retained SQL witnesses from the failed
v33 collection, explicitly labeled NOT_QUALIFIED provenance; current validators
re-executed them into new envelopes. Rules and attributed named tests were fresh
for all20. The old18 retained category checkpoints identify prior receipt refs;
no previous overall qualification was used as current evidence. Original record
fields/scores were preserved. Queue collected all900 fresh cases (2700 executed
formulation witnesses) in36 exclusive25-case checkpoints. No generation occurred.

Verbatim decisive output:

```text
{"pid": 65244, "at": 1792195000.5608742, "phase": "CHEAP_RULES_PUBLIC_JSON_REPLAY_PASS", "contract": "sql.retention.renewal_coverage"}
{"pid": 60484, "at": 1792202850.1010194, "phase": "COLLECTION_PUBLICATION_COMPLETE", "bundles": 20, "category_receipts": 140}
{"pid": 62156, "at": 1792206053.0656242, "phase": "PUBLISHED_QUAL20_SOURCE_BOUND_AUDIT_PASS", "qualified": 20, "quarantined": 42, "registry": 62, "receipts": 140}
```

Final audit artifact:
`scratch/funnel_experiment/engineering/qualified-receipts-v34/final-audit-8013cc8fd77543d095a7711edf6bcfb8.json`.
It independently rediscovered the20 active authoritative bundles, required all
references under v34, reran public qualify for every bundle, checked every
receipt source closure, counted62 latest registry IDs and42 effective latest
quarantines, and rechecked the complete freeze/runtime/budget. The historical
quarantine file is not rewritten or equated with latest effective quarantines.
Its56 retained entries cover52 latest versions plus4 nonlatest versions. Current
public effective-quarantine probes also returned true for all4 nonlatest:
warehouse_throughput@1, inventory_net_flow@1, education_grade_revisions@1 and
logistics_parcel_delivery@1. Thus46 effective quarantined versions means42 latest
plus4 nonlatest, not46 latest IDs. Ten retained latest absence entries are now
effectively resolved by valid public commits; their historical rows remain.
All20 post-publication results are FULLY_VERIFIED with empty reasons; the
authoritative journal/index were updated only through public promote.

Outputs live under `scratch/funnel_experiment/engineering/qualified-receipts-v34/`:
freeze, UUID progress, per-contract task/writer state,140 receipt/checkpoint/public
replay triples,20 bundles/delivery results/post-publication statuses, fresh named
test logs/XML, retained provenance and fresh queue fuzz batches. Foreground owner
PIDs57972/65244/23216/23668/66496/67668/60484/62156 all exited; no detached jobs.
Freeze-to-final-audit elapsed11063.416 seconds; audit progress remains observable
per contract. The first and final900-second collection slices used1200-second
tool timeouts;1800-second slices used2100-second timeouts. Category replay and
promotion are atomic, so slice deadlines stop at their next safe checkpoint.

Budget remains28 physical attempts/400.483 generation seconds; this milestone
used0 of12 model calls. No installs, commits, pushes, role resets, human review or
external sharing. Existing safety() checks emitted Git line-ending/long-path
warnings during promotion; no guard was disabled. Human review PENDING, sharing
BLOCKED. This is runtime qualification, not accepted80, a full-suite certificate,
positive strict export, or an overall score. The parent-owned positive export
test is now unblocked by fresh20 and must run separately as requested.

Post-handoff freeze recheck and four public effective-quarantine probes:

```text
{"freeze_still_stable": true, "source_files": 539, "budget": {"physical_attempts": 28, "generation_seconds": 400.48299999994197, "unfinished_attempts": []}, "nonlatest_effective_quarantine": [["sql.aggregation.warehouse_throughput", 1, true], ["sql.cte.inventory_net_flow", 1, true], ["sql.dedup.education_grade_revisions", 1, true], ["sql.funnel.logistics_parcel_delivery", 1, true]], "model_calls": 0}
```

## v33 — stopped at executed semantic promotion gate

The director-authorized logging-only replan copied `qualification-v32.py` into
`qualification-v33.py`. Differences are the producer/base identity, identity-use
assertion label, UUID import and UUID progress filename. No core/schema/test/
template/authority source edits; no old source hashes updated. No commits,
installs, network, model calls or role changes.

Before freeze, two actual exclusive progress writes were executed with both
`time.time()` and `time.time_ns()` fixed. Verbatim result:

```text
{"pid": 67060, "at": 123.0, "phase": "FIXED_CLOCK_ONE"}
{"pid": 67060, "at": 123.0, "phase": "FIXED_CLOCK_TWO"}
PASS: two exclusive progress writes under fixed time/time_ns; v33 differs only in identity and UUID progress naming
```

Actual command:

```powershell
python -u "NEW v2/qualification-v33.py" freeze; if ($?) { python -u "NEW v2/qualification-v33.py" advance --seconds 900 }
```

Verbatim freeze and decisive execution output:

```text
{"pid": 60452, "at": 1792185423.6709456, "phase": "FROZEN", "originals": 18, "supported": 20, "registry": 62, "source_files": 537, "model_calls": 0}
{"pid": 17416, "at": 1792185595.8842397, "contract": "sql.retention.renewal_coverage", "category": "fuzz", "phase": "RECEIPT", "metrics": {"divergences": 0, "observed_coverage_pass": true, "valid_random_cases": 900}, "elapsed_seconds": 153.48399999999674}
{"pid": 17416, "at": 1792185596.004037, "contract": "sql.retention.renewal_coverage", "phase": "PROMOTE_AND_QUALIFY"}
ValueError: rules: full declared type/nullability checks missing or inconsistent
```

Runtime owner PID17416 stopped by exception; approximately172 seconds from advance
start to promotion attempt. Renewal emitted7 category checkpoints and36 durable
25-case fuzz batches,900 cases total. Named test1 passed; relations2 discriminating,
0 failed; semantic mutants17/17 killed; correct formulations3; witnessed wrong26;
challenge false acceptances/rejections0/0; distinct fixtures4. These are collected
receipts, NOT a qualified bundle: public `promote()` rejected `rules` before
publication. Queue and the18 retained-witness renewals were not reached. No
`CURRENT_QUALIFIED` result was returned. No accepted80/product record was delivered.

Artifacts: `scratch/funnel_experiment/engineering/qualified-receipts-v33/` contains
the new freeze, UUID progress logs, failure traceback and renewal member directory
`sql.retention.renewal_coverage-v1/` with bundle/checkpoints. Original v32 producer,
three receipts and failure were left untouched. Freeze checked budget28 physical
attempts/400.483 generation seconds and stable checks ran through collection.
No successful quarantine resolution; no fresh quarantine census or42/46 claim.

Post-stop audit helper failed three times on diagnostic representation assumptions
(details dict, non-column schema obligation, string domain_checks). It never wrote
an audit report or changed authority; the new helper was removed and not retried.
These failures do not alter the retained public promotion error. No source-bound
final-audit PASS is claimed.

Safe continuation: do NOT resume/refit frozen v33, mutate its receipts or refresh
old hashes. Read the retained rules envelope and public validator at
`src/verified_data_factory/verification/qualification/validation.py:447–457,496–500`.
Determine the exact retained-versus-recomputed schema-check mismatch outside this
logging-only brief. The error identifies an equality gate, not yet a proved root
cause. Any source/controller repair requires a new identity and pre-freeze check.
No inference until20 source-current qualified bundles exist. Human reviewPENDING,
external sharingBLOCKED; full-suite certificate and record delivery remain pending.

## v34 runtime delivery — infrastructure stop before inference

New Temp controller `revo_delivery_v34_runtime.py` reconciled budget28/400.483s,
checked all v34 frozen source hashes and runtime, and capped planned6 calls against
the milestone12/global360/14400 limits. No Python workers or loaded Ollama models
were observed before launch. Existing `freeze(cpu=True, tasks=((id,1),),
candidates_per_task=3)` created unused renewal run
`runs/company-renewal-coverage-cpu-v34-001`; existing `execute()` stopped in
production preflight before any model call:

```text
ValueError: shared production preflight failed; no inference performed
```

`preflight.json` reports sandbox image expected/actual digest matching, but
`sandbox.ok=false` due to stale containers `94b67fd6be46`, `677acffde130`,
`e456169bbb2f`. Read-only Docker inspection confirmed all three exited/not running.
No container cleanup or retry authorized/performed. Infrastructure stop prevents
queue freeze/execution; its proposed run identity remains unused. No SQL was
generated or compared: raw/executable/correct/STRONG/duplicate/eligible/admitted/
replayed all0 for both tasks, NOT a failed SQL claim. No quality/export/product/
sidecar/replay/registry mutation. Original reports and prior archives untouched.

Evidence: `NEW v2/runtime-delivery-v34/`, original renewal protocol/binding/preflight,
and new durable `artifacts/internal-deliveries/v32/renewal-runtime-v34-blocked/`
with byte inventory. No delivered package exists to add to the consolidated pool;
existing inventory was not clobbered. Batch elapsed62.464064598083496s; model calls0,
generation seconds0, cumulative28/400.48299999994197, milestone remaining12,
program remaining332 calls/13999.517000000058 seconds. Parent must resolve the
infrastructure blocker; do not resume the stopped run. No CORE SQL defect proved.
Accepted frozen80=0; company examples0; score NOT_COMPUTABLE; human review PENDING,
sharing BLOCKED. Prior full3h timeout plus repaired-test tail remains no full cert.

## v35 — final fresh20 and actual queue delivery/replay complete

New frozen producer `NEW v2/qualification-v35.py` uses the established v34
runtime receipt/publication recipe with a new destination and current source
closure. Freeze:542 inputs,20 retained authoritative records, budget33 physical
attempts/468.49799999995594s,unfinished0. No old producer, source hash, receipt,
core/scripts/tests/templates or original run was rewritten. The initial read-only
Git status and existing safety/public promotion guards emitted Git warnings;
there were no Git writes, commits or installs. The TS/Swift mapper found0 files
in this Python source tree; actual Python interfaces were read before runtime work.

Cheap fresh RULES -> JSON serialization -> independent public receipt replay
passed before collection. All20 received fresh rules and attributed named tests;
retained900-case witnesses were replayed through current validators and independent
serialized public receipt checks, not regenerated. Renewal retained the unchanged
v33 witness detail via the immutable v34 recipe; the other profiles used their
retained authoritative evidence. Public promote and public qualify completed for
each profile. Checkpoint results after bounded slices:7-category partial slice,
then13 completed/91 receipts,19/133,finally20/140. Owner PIDs40496,47948,8876,21724
exited at safe checkpoints. No failed helper/retry or new model call occurred.

`final-audit-e6e5b4082c924eab9340f0235cfb4772.json` under
`scratch/funnel_experiment/engineering/qualified-receipts-v35/` binds the20
completed individual public qualifications to current sources, receipt references,
active journal/index and bundles. It deliberately does not rerun20 full SQL
qualifications. Latest62/qualified20/quarantined42; four nonlatest public quarantine
probes also returnedtrue, making46 effective quarantined versions, not46 latest.

Actual unchanged queue run `company-queue-batches-cpu-v34-002`,slot0 was bound to
original protocol digest,physical attempt journal,request,sampling and parsed JSON
`http-response.json.body`. New native sandbox execution SUCCEEDED; native verifier
PASS/STRONG,18 semantic kills,mutation1.0,coverage complete. Real analyze/export of
the one-record pool selected exactly1 Golden.19 retained expected-result objects
in this actual verification have `exact_column_types:true`. Original slot0
INCONCLUSIVE report and slot1 WINDOW parser failure,raw responses,timestamps and
protocol remain byte-identical; slot1 was not rejudged or admitted.

Supported `prepare(pool=...)` admitted the actual original slot to a new packet.
Strict INTERNAL TRAIN/train1/engineering_group build was VALID/exact1 record using
the fixed source-root company-model-role registry and its authority pointer.
Durable bytes live at `artifacts/internal-deliveries/v32/queue-v35/delivery/`.
The Windows-aware stdlib driver was separately SHA-pinned, copied, and actually
executed against a NEW relocated copy; it reported VALID/record_count1/file_count11749.
JSONL/Parquet roundtrip exact1; membership/SQL substitution,recomputed editable
checksums and TRAIN-to-EVAL were REJECTED. The EVAL rejection left the actual
registry unchanged. TRAIN registration uses persistent authority,not a local
substitute. Original run and budget journal bytes were rechecked unchanged.

Proof commands: `qualification-v35.py freeze`, `preflight`, bounded
`advance --seconds 1800` slices, `audit`; Temp `queue_v35_delivery.py rejudge`,
`build`, `replay`, then `queue_v35_close.py`. Controllers are retained with hashes
under the durable queue-v35/controllers directory; `final-proof.json` records
the exact closure, separate driver/manifest/anchor pins,counts,timings and budget.
Freeze-to-delivery8829.998104810715s. No detached workers remain from these commands.

Decisive actual output:

```text
ACTUAL_QUEUE_PASS_STRONG_ONE_GOLDEN
QUEUE_STRICT_BUILD_VALID_DURABLE
```

```json
{"status":"VALID","errors":[],"warnings":[{"check":"release.quality.unchecked","passed":false,"detail":"no quality evidence supplied; mutation/contamination gates cannot run"}],"record_count":1,"file_count":11749,"checksum_status":"ok","schema_status":"ok","split_status":"ok","provenance_status":"ok","manifest_status":"ok","schema_version":"1.0"}
```

The parent renewal `reviewer/renewal-io-proof-round2/report.json` already proves
DONE_RENEWAL_REPLAY/exact1; it was checked,not rebuilt. Combined target deliveries2
(retention+window),not accepted80 or company samples. Budget remains33/468.498s,
unfinished0; this work used0 model calls,milestone remains5of12,not40 used.
Root quality context unsupplied means `release.quality.unchecked` remains; no flag
cleanup,complete quality certificate,full suite or broader measurement claimed.
Human reviewPENDING,sharingBLOCKED,accepted80=0,company samples0,scoreNOT_COMPUTABLE.

Post-ledger read-only helper initially raised `KeyError: 'manifest_sha256'` by
looking for manifest/anchor pins in final-proof rather than durable-origin.
Retained `queue-v35/final-pin-check-failure.json`; no package/source/pin mutation.
Recovery reads the existing immutable durable-origin pins only.
