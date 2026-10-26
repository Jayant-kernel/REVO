# Automated pre-review checkpoint — V21, 2026-10-09

**The continuous program is incomplete.** Current catalog: **57 contracts,
10 FULLY_VERIFIED / 47 QUARANTINED across nine qualified families**. Accepted
forward 80-record candidate: **0**. Engineering score **NOT_COMPUTABLE**.
Human review **PENDING**, model utility **NOT_MEASURED**. This is a local
engineering checkpoint, not a commercial release or dataset acceptance.

## 1. Completed implementation and evidence

Added exact clause/schema/output proofs, three substantive correct formulations,
20+ witnessed executable wrong queries, two discriminating relations, four
fixtures and full observed three-seed campaigns for five profiles:

| Contract/version | Family | V21 status |
| --- | --- | --- |
| sql.joins.logistics_final_leg@1 | multi_joins | FULLY_VERIFIED |
| sql.cte.order_line_reconciliation@1 | cte | FULLY_VERIFIED |
| sql.windows.media_previous_play@1 | window_functions | FULLY_VERIFIED |
| sql.temporal.clinic_weekly_visits@1 | temporal | FULLY_VERIFIED |
| sql.retention.saas_repeat_payment@1 | retention | FULLY_VERIFIED |

Existing fulfillment SLA@1, manufacturing scrap@1, SaaS activation/payment@2,
SaaS paid invoices@1 and EXISTS@2 were freshly recollected and renewed as well.
Each of the ten V21 bundles retains all seven categories, 900 random cases
(300 for each seed 1/43/94001) and 2700 actual correct-formulation executions.
These correlated executions are not independent authored tasks or product rows.

Repairs proven by retained failing reproductions:

- Final-leg dictionary lookup collapsed leg/carrier bags: actual SQL returned
  eight rows versus the old oracle's two. Preserve all three input bags; oracle
  implementation identity is now 3, public contract remains version 1.
- Reconciliation reference overflowed INTEGER multiplication before SUM. Widen
  quantity to HUGEINT before multiplication, preserving exact integer arithmetic.
- Playback oracle sorted NULL/integer predecessors as an undeclared output tie
  rule when play IDs repeat. Sort by only the declared play_id; identity is 3.
- Normal hidden verification omitted required clause/challenge counterexamples.
  The backend now executes them, source-tagged REQUIREMENT_COUNTEREXAMPLE, for
  supported versions and all candidate formulations. Original independent fixtures
  and the four-fixture derived-diversity requirement remain separate.
- The receipt wire model now explicitly recognizes the five new observation
  policies. Unsupported policies fail a cheap preflight before 2700 SQL runs.
- Attributed named tests use the authoritative typed comparator, including actual
  SQL column types, rather than Python DATE-versus-ISO-string list equality.
- The E2E test requires the original four hidden cases plus the exact new clause
  fixture count, with every added case passing and derived diversity unchanged.

Latest bundles: `scratch/funnel_experiment/engineering/qualified-receipts-v21/`.
Post-regression catalog: `scratch/funnel_experiment/engineering/catalog-auto-quality-v21.json`.
Durable task/criterion ledger:
`scratch/funnel_experiment/engineering/AUTOMATED-QUALITY-LEDGER-20261009.md`.
V17 and all failed/intermediate V18–V20 evidence remain retained under their
original identities. Original quarantine manifest is preserved; promotion uses
the existing journal/index transaction and exact missing-evidence resolutions.

## 2. Full catalog and coverage

All 57 latest registered contracts remain in the denominator. Qualified families:
aggregation, cte, funnel, multi_joins, retention, simple_joins, subqueries,
temporal and window_functions. **Deduplication remains missing.**

Grade revisions@1 are unsuitable for promotion without a specification decision:
two valid rows can share student/course/recorded_at/revision_id but have different
grades. Highest timestamp/ID does not select a unique payload; schema declares
no uniqueness. The retained reproducer demonstrates insertion-order-sensitive
oracle selection on schema-valid inputs. Do not invent a winner or rewrite history.

47 unqualified contracts remain. Five of the former 36 named-oracle candidates
were completed; the remaining 31 candidates require inspection/engineering,
including the newly identified grade tie dependency. Do not assume every named
oracle is well-specified. Preserve the sixteen historical semantic/schema cases
listed in the V17 summary, separately from this newly narrowed dependency.

## 3. Forward candidate and diversity gates

Accepted rows **0/80**, per-family accepted rows **0/8 in all ten families**.
No forward acceptance artifact establishes 40 materially different instructions,
10 schema roles/five domains, <=12 rows/schema, 16 constructs/15 edges,
duplicate disposition, candidate provenance, STRONG verification or role
isolation for a composed product. Qualification cases and one-row export probes
do not fill these quotas. Ten qualified instructions cannot supply forty.

## 4. Real generation and budget

New model calls **0**; attempts **0/360**, cumulative generation time **0/4h**.
No model-generated forward population exists; yield is not measured, not 100%.
`ollama list` found six installed models. The recorded Devstral derivative is
REVIEW_REQUIRED with unknown commercial-use/distribution evidence; other installed
models have no applicable recorded ledger entry. Installation is not rights proof.
Generation remains incomplete and task-diversity-gated. No installations, model
downloads, paid/cloud services, credential changes or external contacts occurred.
Keep any future attempts/resumes under the same budget and ledger.

## 5. Checker comparison and limits

Freeze protocol before results, using the same 30 correct / 223 known-wrong SQL
population across ten supported contracts (nine families). Retain full tasks,
SQL, initial executions, typed comparisons, verifier results, input sizes,
resource limits and real Docker lifecycle/cleanup observations for every case.
Report verdict acceptance separately from STRONG admission.

First result is retained as development evidence:
`checker-comparison-v19-r1/report.json`: execution-only accepted 223 wrong,
ordinary comparison 40 wrong, full verifier 20 wrong, 27 correct accepts and
seven abstentions. This result informed the runtime counterexample repair.

Latest current-source measurement:
`scratch/funnel_experiment/engineering/checker-comparison-v21-r3/report.json`,
frozen by `checker-protocol-v21.json` with ordinary-fixture seed 314159:

| Checker | Correct accepted /30 | Wrong accepted /223 | Wrong rejected /223 | Abstentions |
| --- | ---: | ---: | ---: | ---: |
| Execution only | 30 | 223 | 0 | 0 |
| Ordinary typed fixture comparison | 30 | 41 | 182 | 0 |
| Full verifier | 27 | 0 | 223 | 3 (correct queries) |

Zero false rejections, observed infrastructure failures, invalid initial SQL or
checker exceptions. Local measured case wall time 1047.211s; paid-service cost
zero, monetary local compute cost not measured. All full-verifier abstentions
remain explicit: generic mutation coverage is weak for three correct alternatives.
Unsupported candidate transforms do not borrow canonical STRONG proof.

The challenge population shares authoring with the checker and informed repairs;
new ordinary seeds share fixture algorithms and are not independent business
scenarios. This is finite curated development-regression evidence, not held-out
generalization, population error prevalence, universal equivalence or model utility.

## 6. Replay, recovery, realism and source certification

Full regression r2: **1544 passed in 6012.30s (1:40:12)**, zero failures,
errors, skips or deselections; no pytest warnings reported. `junit_family=xunit1`
retains attributed properties. Git emitted retained line-ending advisories during
identity capture. Strict mypy: **182 source files**, no issues. Scoped Ruff PASS.
Frozen rubric/assets and paused-run 15-file guards PASS in every completed wrapper.

The full suite includes actual typed export/relocation and tamper rejection,
authority resolution/renewal, source-staleness rejection, real process-kill
generation/evaluation/recovery and the complete new 900-case campaigns. Those
tests are engineering probes, not certification of a nonempty 80-row export.
Broader interruption/distributional coverage remains due.

Current all-57 cardinality diagnostic:
`scratch/funnel_experiment/engineering/realism-auto-quality-v21.json`.
All 57 have at least three observed matching cardinalities across empty,
minimal-prefix, boundary-seed and eight-copy profiles. This does not establish
complete public-domain conformance, skew/sparsity/fanout/long-history realism,
or remove any quarantine. Earlier SLA backend abort remains unexplained;
no new infrastructure failure in traced comparison proves its historical cause.

Regression source identity, HEAD unchanged on local main:

```text
HEAD: 22ecfeb4e8a92c7c4909c11197dee1e455c4f500
tracked_diff_sha256: e1242909bb4686e3abbe7e3180a1a237e5695d2b4514620413234788e7062695
untracked_source_content_manifest_sha256: 419aeaf9b91d8587f46cb3ad864e550fa1bcd4315a2922d3d215a8f4d6bca29d
per_file_manifest_sha256: 457c9535201ba67d65d269d25619239d61ba9e14f373923a11f0cd39e61dce09
```

Every completed command retains matching launch/post identities and exact command
under `C:/Users/jayan/AppData/Local/Temp/opencode/revo-auto-quality-20261009-*`.
Primary directories: `refresh-v21`, `full-r2`, `mypy-final`, `ruff-final`,
`catalog-v21`, `realism-v21`, `checker-freeze-r3`, `checker-run-r3`.
JUnit: `revo-auto-quality-20261009-full-r2.xml`. Documentation added after the
regression is not retroactively claimed as part of its byte snapshot.

Post-documentation read-only binding probe `revo-auto-quality-20261009-binding-v21`
passed all **70 category receipt** hashes/current dependency closures across ten
contracts; executable source still matches the regression snapshot. Original
quarantine manifest bytes and paused-run guard remain unchanged. This probe checks
binding, not repeat SQL execution; the post-regression catalog supplies SQL replay.
Probe path: `C:/Users/jayan/AppData/Local/Temp/opencode/revo_auto_quality_binding_v21.py`.
Probe SHA-256: `d1bf8cf59d66ed4a28d6a99e8f9186b3a9f9a875280f223a745832eaf71b3d74`.
V21 readiness SHA-256: `4c3c3f4d7498f85bd9422eed342649e61c7e1d6e45232385a2af4da997fa1461`.

Failures/interruption retained: initial join/overflow/playback red cases, surviving
ID-only history discriminator before its fixture repair, FuzzDetail policy failures,
V18 clinic named-test DATE mismatch, catalog r1 timeout, full r1 interruption with
no terminal report, and the old E2E hidden-count red case. None is relabelled PASS.

## 7. Frozen scoring

**NOT_COMPUTABLE**. No frozen scorer invoked. All 24 criterion-specific metric
receipts remain to be produced/validated for their required populations. The
ledger inventories their exact unchanged names and missing executed inputs.
Current tests, cardinality diagnostics, qualification counts and the curated
checker report cannot substitute for those metrics or shrink 57 to ten.
Accepted candidate/final dataset protocol and full coverage/dispositions remain
missing. Historical commercial 52/100 and historical 232 rows are separate evidence.

## 8. Resumable next work

This checkpoint does not finish the autonomous queue. Continue safe specified
engineering without waiting for grade-owner intent or model rights:

1. Inspect/qualify the next named business profile, e.g.
   `sql.aggregation.warehouse_throughput@1` (HAVING threshold coverage), then
   meaningful additional contracts until forty distinct instructions are possible.
2. Keep grade tie ambiguity quarantined; inspect other dedup contracts for a
   genuinely complete public domain before attempting ten-family coverage.
3. Implement proven candidate-derived transforms for correct alternative SQL
   formulations; preserve UNKNOWN/WEAK for unsupported transforms and current caps.
4. Execute targeted skew, sparse/empty, many-to-many fanout, duplicate payload,
   large numeric and long temporal-history cases. Minimize observed failures.
5. Broaden interruption/publication/replay coverage and bounded backend diagnostics.
6. After sufficient qualified diversity and an eligible recorded local provider,
   freeze <=60-attempt batches, generate, verify/admit and select the exact 80 rows.
7. Build fresh criterion producers and final candidate/export certification before
   any score or post-acceptance preview. Keep rights decisions distinct from proof.

Replay tools (always use unused output paths and preserve failed attempts):

```powershell
python -B -m scripts.engineering_program_audit --output <unused-catalog.json>
python -B -m scripts.engineering_realism_profiles --output <unused-realism.json>
python -B -m scripts.engineering_checker_comparison --protocol <unused-protocol.json> --freeze --seed <reserved-seed>
python -B -m scripts.engineering_checker_comparison --protocol <frozen-protocol.json> --destination <unused-case-directory>
python -B -m pytest -q -o junit_family=xunit1 --junitxml <unused-report.xml>
python -B -m mypy src --strict
```

Wrap certification commands with `scripts.engineering_program_evidence` to retain
source identities and guards. Any relevant edit requires new immutable receipt
collection and affected certification; do not replace old hashes with new ones.

## 9. Review and distribution boundary

Human review **PENDING**. No commercial/company approval, outreach, public preview,
release, commit or push. Original substantial modified/untracked work is retained.
No 10–20-example preview is labelled ready before automated candidate acceptance.
Authorship remains **differential verification; independent authorship unproven**.
