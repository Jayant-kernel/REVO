# Golden Dataset Remediation Result

## Scope and outcome

**FACT** — Historical run directories were not rewritten. The final controlled
requalification is stored at `runs/controlled-requalification-002`.

**MEASURED** — The final export contains 46 Golden records, 11 records held for
human audit, and 0 excluded records. Method: counted JSONL lines and read
`run-state.json`.

**MEASURED** — The export has 46 unique `record_id` values and 46 unique
`candidate_id` values. Method: parsed `quality/export/golden.jsonl` and counted
distinct values.

**MEASURED** — All 46 Golden records have `STRONG` verification and mutation
score 1.0. Method: grouped the embedded verification fields in the Golden JSONL.

**MEASURED** — All 46 provenance chains are complete, graph validation reports
0 problems, and all 160 artifact references resolve to files inside the bundle.
Method: ran `factory provenance validate` and checked every `relative_locator`.

**MEASURED** — The final complete project suite passes: 662 tests passed in
375.81 seconds.

## Applied phases

### Phase 1 — Integrity foundation

**FACT** — Golden records now carry a SHA-256 identity bound to schema version,
task, instruction, schema, and candidate SQL. Legacy records receive the same
identity deterministically when loaded.

**FACT** — Product transforms use `record_id` rather than `candidate_id` as the
Golden record identity.

**FACT** — Strong-verification policy now accepts only `STRONG`; `UNKNOWN` and
`WEAK` do not qualify.

**FACT** — Duplicate representative selection only considers records that remain
eligible for Golden selection.

**FACT** — Contamination health output now preserves `flagged_count`,
`split_overlap_count`, and counts by flag type.

### Phase 2 — Semantic verification

**FACT** — Executable semantic kills, survivors, invalid mutants, and
infrastructure-inconclusive mutants are represented separately. Invalid SQL no
longer raises mutation score.

**FACT** — Window v2 exposes `order_date` and `previous_amount`, defines NULL
ordering and LAG behavior, and has a NULL-aware independent oracle.

**FACT** — Retention v2 defines calendar-date timestamp interpretation and
materializes before-signup, day-30, and day-31 fixtures.

**FACT** — Funnel v3 defines `(event_time, event_id)` ordering and materializes a
same-timestamp full funnel.

**FACT** — Temporal generation materializes a timestamp at 23:59:59 on the final
included day.

**FACT** — Historical Window v1, Retention v1, and Funnel v2 templates remain
available for replay. The final Golden export explicitly excludes Window v1
because its contract contains the audited LAG/output inconsistency.

### Phase 3 — Release and evidence safety

**FACT** — Public release validation now requires a supplied quarantine set,
per-row quality evidence, `STRONG` verification, passed human audit, and an
explicit commercially cleared supply-chain report.

**FACT** — Public product rows fail validation if internal execution,
verification, raw-response, fixture, requirement, stdout, or stderr fields are
present.

**FACT** — Provenance bundle construction resolves task and selection roles
through graph edges, includes source and environment snapshots, and uses
content-bound record IDs for snapshot membership.

**FACT** — Provenance export writes and hash-checks referenced raw, SQL, and
Golden artifacts inside the bundle.

### Phase 4 — Production controls

**FACT** — The production runner implements resumable batches, pre-generation
task and candidate caps, wall-time checks, target stopping, audit sizing, pause
conditions, and persisted stop reasons. Each explicit execution authorization is
limited to one batch and then requires review before continuation.

**FACT** — A fresh-generation configuration targeting 60 records is preserved at
`configs/production/controlled_qualification_60.yaml`.

**FACT** — The slower fresh-generation run was stopped after 27 checkpointed task
bundles when controlled requalification provided a faster, stricter path. Its
partial artifacts remain at `runs/controlled-qualification-060`.

### Phase 5 — Controlled qualification

**FACT** — The first pass requalified all 67 prior Q5 Golden candidates and
produced 54 Golden records plus 13 audit-held records.

**FACT** — The final pass removed 10 legacy Window v1 source candidates. Of the
remaining 57, 46 became Golden and 11 remain held for human audit.

**MEASURED** — The final 46-record dataset covers two families: 18 CTE records
and 28 temporal records. Family coverage is 2/10, construct coverage is 10/16,
and edge-case coverage is 3/17.

**MEASURED** — Six records carry soft `EXACT_OVERLAP` flags, and split overlap is
zero. These flags describe sibling/task overlap in the analyzed population; the
evidence does not establish external benchmark contamination.

## Revised buyer-oriented score

**INFERRED** — The current commercial-data-product score is **52/100**, up from
36/100. This uses the same buyer-oriented rubric as the original audit. It is a
reasoned assessment with roughly five-point sensitivity, not an industry
certification or measured SQL accuracy percentage.

| Dimension | Weight | Current | Receipt for remaining deduction |
|---|---:|---:|---|
| Semantic correctness assurance | 15 | 13 | **MEASURED** — All retained rows pass corrected verification, but no independent expert semantic review exists. |
| Verification discrimination | 15 | 13 | **MEASURED** — 46/46 are strong with mutation score 1.0; evidence covers only two retained families. |
| Instruction quality and task independence | 10 | 6 | **FACT** — Temporal instructions remain close to query recipes and instruction variety is narrow. |
| Diversity and independent coverage | 15 | 2 | **MEASURED** — Only 2/10 families and 3/17 edge-case categories are represented. |
| Realism and demonstrated difficulty | 10 | 2 | **FACT** — Fixtures remain small synthetic retail workloads and difficulty is declared rather than empirical. |
| Human review and adjudication | 10 | 1 | **MEASURED** — 11 sampled records are pending; the 46 Golden rows do not have completed independent review evidence. |
| Identity, provenance, reproducibility | 10 | 9 | **MEASURED** — IDs, chains, graph, and artifacts validate; an independently reproduced second environment is still absent. |
| Separation and contamination assurance | 5 | 4 | **FACT** — Public release gates and field filtering are enforced; external fingerprint coverage remains absent. |
| Rights and commercial clearance | 5 | 0 | **FACT** — No approved release-specific rights packet was supplied. Public release therefore fails closed. |
| Documentation and demonstrated utility | 5 | 2 | **FACT** — Results and limits are recorded; no buyer utility experiment or model-improvement result exists. |
| **Total** | **100** | **52** | **INFERRED** — Technical trust improved materially; breadth, review, rights, and utility remain the largest deductions. |

## Score after remaining improvements

**INFERRED** — A defensible score after completing the remaining evidence work is
approximately **89/100**. This requires actual evidence, not code changes alone:

- **MEASURED requirement** — expand retained coverage from 2/10 to all 10
  families with materially different instructions, schemas, and edge cases.
- **FACT requirement** — independently review every released row and resolve all
  disagreements; the 11 current audit items cannot be auto-approved.
- **FACT requirement** — obtain release-specific commercial rights approval for
  the model/checkpoint, upstream components, and intended output distribution.
- **MEASURED requirement** — run a held-out buyer-relevant utility experiment and
  report the baseline, protocol, uncertainty, and attributable result.
- **FACT requirement** — reproduce the release in a second environment and retain
  the resulting attestation.

**INFERRED** — The current dataset cannot honestly score above 85 because four
high-weight evidence categories remain unfulfilled: diversity, human review,
commercial rights, and demonstrated utility.

## Where I was too generous

**INFERRED** — The 13/15 semantic score may be generous because all retained rows
come from only CTE and temporal families. Evidence that would lower it is an
independent review finding a shared oracle/specification error. Evidence that
would support it is reviewed counterexamples and a second implementation.

**INFERRED** — The 13/15 verification score may be generous because hidden cases
share the project’s fixture generator. Evidence that would lower it is a mutant
or independently authored fixture that the verifier wrongly accepts. Evidence
that would support it is external adversarial testing across all families.

**INFERRED** — The 9/10 provenance score may be generous because graph
completeness proves resolvability, not truthfulness of every upstream claim.
Evidence that would support it is independent replay from the exported bundle
and attestation of the model/source identities.

**INFERRED** — The 52/100 total may still overstate practical purchasability. A
strict buyer can treat unresolved rights and absent independent review as binary
rejection conditions. With ten times more review time, the first checks should be
row-level semantic adjudication, external contamination matching, checkpoint
rights, second-environment replay, and a held-out utility experiment.
