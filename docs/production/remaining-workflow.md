# Verified Data Factory: remaining workflow

## Latest local evidence — 2026-10-01

See `quality70-result-20261001.md` for the separately identified new-dataset
assessment and verified remaining-work register. Local changes add seven tested
business IDs (21 total, at least two per family), production sandbox/resume/budget
repairs, and review membership/identity regression checks. A bounded diverse
smoke generated 60 candidates, selected 15 Goldens across ten families and
replayed all 15 successfully on the same host. Final suite: 766 passed.
The new diagnostic assessment is 59/100, not 70; the historical 46-row 52 score
is unchanged. The premium four-template-per-family preflight is still blocked;
no 80-row qualification or commercial release occurred. The register below is
the earlier implementation snapshot and its measurements are historical.

Updated 2026-09-30. This is a status register, not release authorization.
The master handoff and `docs/release-93-spec.md` remain the acceptance sources.

## Verified implementation evidence

- The earlier `python -m pytest -q` result was **629 passed, 72 skipped in
  194.77 seconds** on 2026-09-30 while Docker Desktop was stopped. This is
  historical evidence, not the current Docker-enabled suite result.
- Docker Desktop was subsequently started. SaaS, payments, support-SLA, and
  education grade-revision templates passed the real sandbox and full verifier
  with STRONG evidence, mutation score 1.0, and a passing independently authored
  adversarial hidden case each. The current Docker-enabled suite passed
  **718 tests with no skips in 541.69 seconds** on 2026-10-01. A separate local DuckDB sweep of the
  support-SLA template across 100 deterministic seeds found no surviving
  applicable SQL mutants; this is not a production dataset run.
- Earlier, before the new SaaS/payments templates and 4.3 gate, the full
  suite had **680 passed in 349.89 seconds**, with a focused Docker matrix of
  **32 passed**. These are historical checks, not evidence for the new tasks.
- The new SaaS/payments generators and independent oracles agree with
  hand-authored SQL over three seeds. The new financial amounts use signed
  integer minor units, avoiding binary-float ledger arithmetic. Their generated fixtures kill at least
  three applicable SQL mutants per template, and separate adversarial rows
  exercise the key exclusions. The Subquery v2 fixture distinguishes
  `amount > 500` from `amount > 0` in DuckDB over three seeds.
- Focused new-template/runner/oracle/mutation checks: **81 passed**.
- Ruff checks passed on changed Python files; strict mypy passed on the new
  review/measurement modules and checked release/production models plus the
  new fixture/oracle/metamorphic code.
- The current 4.3 premium `production plan` is read-only and reports
  `template_diversity.ok=false`. Current preflight passes Docker, the pinned
  sandbox image, model digest, storage, configuration, and pipeline checks; it
  fails only the four-template-per-family diversity gate. Neither command
  generated candidates or started a run.
- `git diff --check` passed. The new research note remains untracked; no
  historical run artifacts were edited and no changes were pushed.

| Step | State | Evidence and next acceptance condition |
| --- | --- | --- |
| 1. Measurement and plan reconciliation | In progress | Research note corrected; new population report and cross-task stop have tests. The frozen edge coverage denominator is again 17 despite six extra domain fixture labels. External corpus matching and release-level near-duplicate review remain. |
| 2. Checkpoint governance | Awaiting authorized rights owner | Exact smoke digest recorded in its manifest; current status is `REVIEW_REQUIRED_NON_COMMERCIAL`. See rights packet below. |
| 3. Smoke diagnosis | In progress | Subquery weak-suite and Funnel candidate failures identified in `smoke-diagnosis-001.md`; independent adversarial reproduction remains. |
| 4. Task-library expansion | In progress | Forty business questions across ten distinct schema designs are drafted in `task-coverage-matrix.md`; four are implemented as separate SaaS, payments, support-operations, and education template IDs with independent oracles. The other 36 are designs only. Subquery v2 is a repair, not a new business task. |
| 5. Fixture validation | In progress | Subquery v2 threshold fixture discriminates the surviving SQL mutant in DuckDB over three seeds. SaaS, payments, support SLA, and education grade revision tasks have deterministic boundaries and one hand-authored adversarial case run in the real sandbox as additional hidden evidence. The premium pre-review screen requires a passing independent case per row. Other templates still need independently designed runtime fixtures and validation. |
| 6. Durable human review | Partially implemented | Frozen package, append-only decision journal, adjudication, and derived quality evidence have tests. `review-freeze --premium` rejects a pool that fails measurable 80-row pre-review gates; default freeze is labeled diagnostic. PUBLIC release validation requires final PASS for shipped rows. A PUBLIC product explicitly claiming `PREMIUM_93` additionally requires a premium-qualified 80-row review package, final PASS for all 80, and matching derived review-package IDs in quality evidence. Reviewer authentication and manual semantic/AST checks remain. The old `quality audit` command is unchanged. |
| 7. New diverse smoke | Not run | Need two independent tasks per family, versioned configuration, local preflight, and execution authorization. |
| 8. Controlled 80-row pool | Not run | `factory quality premium-check --golden <path>` now reports measurable composition and automated-evidence gaps without generating anything. On the historical 46-row product it reports 2 families, 2 distinct instructions, 2 schemas, 10/16 constructs, and 3/17 tracked edges; on smoke it reports only 6 rows. It does not prove material novelty or external cleanliness. |
| 9. Frozen review package and replay | Not prepared | Needs content-bound package and clean-environment replay evidence. |
| 10. Human review | Awaiting people | Every released row requires two blind decisions, adjudication of disagreements, final PASS. |
| 11. Utility and release | Awaiting evidence | Rights, independent replay, preregistered utility, documentation, and approvals remain. |
| 12. Expansion | Deferred | Use observed novelty, coverage, utility, and cost per novel Golden after qualification. |

The current 52/100 score is a house commercial-readiness assessment of the
46-row controlled requalification product. It is not measured SQL accuracy or
an assessment of all historical Goldens.

The new read-only `factory quality premium-check` reproduces the 46-row
product's key composition deficits: 2/10 families, 2 exact instruction texts,
2 schemas, 10/16 constructs, and 3/17 frozen edge categories. It also shows
that the 232 Production-001 Goldens are 7/10 families, 7 exact instruction
texts, 5 schemas, 12/16 constructs, and 12/17 frozen edge categories. The
232 candidate-level contamination flags need population-level adjudication;
they are not evidence of 232 external benchmark matches. Exact text variety
is only a screen, not proof of materially different instructions. Neither
historical set meets the premium review-pool specification.

Under the 52-point rubric, removing the review (9 missing points) and rights
(5 missing points) deductions still caps a hypothetical pre-review,
uncleared product at 86/100 even if every other dimension were perfect. This
is an arithmetic ceiling, not a new score. A 70+ *technical* shadow assessment
could become plausible after a genuinely diverse, verified pool and empirical
difficulty evidence; the frozen commercial-readiness score is not raised by
code, templates, or raw row count alone. A 90+ claim requires human review,
rights, independent replay, and buyer-relevant utility evidence.

## Measurement contract for new runs

`quality/export/population_metrics.json` reports sibling candidate rows,
cross-task semantic collisions, selected Golden collision members, and
cross-role task/template/schema overlap with explicit denominators. The runner's
configured `semantic_duplicate_rate` pause now measures the fraction of
distinct tasks participating in a semantic fingerprint group spanning multiple
tasks. This excludes the expected three sibling candidates for one task.
The historical smoke report retains its original candidate-level figures.
The premium pre-review screen now reports soft `EXACT_OVERLAP` flags separately
as `candidate_sibling_exact_overlap_flags` only when new quality evidence marks
their scope `SAME_TASK_SIBLINGS`; these are not treated as external benchmark
matches. Historical flags without a recorded scope remain unresolved. It fails on
selected-row semantic or structural fingerprint collisions and any other
unresolved contamination flag. Fingerprints still require manual assessment
before a no-near-duplicates claim.

Semantic and structural fingerprints are screening heuristics. The current
known-source registry has no identified external benchmark corpus; external
benchmark overlap is `NOT_MEASURED`, regardless of internal `EXACT_OVERLAP`
flags. A versioned reference registry and matching report are required before
an external cleanliness claim.

## Pre-generation coverage matrix

Design at least four materially different questions per family before a
60-attempt smoke. Each row in the design matrix needs: domain, schema
fingerprint, business question, required constructs, edge cases, oracle
contract, normal fixture, boundary fixture, independent adversarial fixture,
and a plausible wrong SQL solution that the verifier rejects. Track the ten
families against at least five domains and ten schemas. A new seed or table
rename does not complete a matrix cell.

## Review and release distinction

A small diagnostic review can inspect failed and inconclusive examples to find
defects. Its yield is not a release acceptance rate. The final package must
contain review-eligible survivors only and must meet every criterion in
`docs/release-93-spec.md`, including review and adjudication for every row.

The new `factory quality review-freeze`, `review-decide`, `review-status`, and
`review-export` commands support a content-bound manual review package. Use
only automatically selected, verified candidate rows as its input. The
`review-export` command creates derived quality evidence in a new directory
after every item has final PASS. It does not alter the source Golden JSONL or
historical run. Reviewer IDs are operator-supplied identifiers, so a review
coordinator must verify human identity and preserve blind access controls.
The PUBLIC release validator now also checks the frozen review package for
final PASS on every shipped row. A coordinator must still verify human identity
and confirm that the full premium composition and evidence requirements pass.
New product manifests use schema version 1.1 and bind the explicit
`acceptance_profile` (`STANDARD` or `PREMIUM_93`) into the product configuration
identity. A public `PREMIUM_93` build cannot use a diagnostic review package or
quality decisions derived from a different frozen package. This is a claim gate,
not proof of market-leading performance or rights clearance.

The premium 80-row config is now version 4.3 and explicitly uses
`review_pool_mode`. It selects automated survivors without blocking all
candidates on the audit sampler, then writes `review_queue.jsonl` for those
survivors. The rows remain pending human review. The earlier smoke and its
audit selection are unchanged.
The runner now rotates deterministically through the latest version of each
distinct template ID in a family and pins the selectable template catalog
hash in every new run manifest. A changed catalog cannot resume under the
same run identity.
New run manifests also pin SHA-256 content hashes of the quality, sandbox,
provenance, and product policy files. A changed referenced policy, even at the
same path, requires a new run identity. The premium quality policy is version
`2.1-premium-93-scoped-overlap`; old unscoped overlap flags remain unresolved.
The premium preflight also requires four distinct template IDs per family
before any costly run. Current availability is 2 for simple joins and
deduplication, 3 for aggregation, and 1 for each other family, so it is
intentionally blocked.

Production-002 remains prepared and unauthorized. No historical run is changed
by this plan. Before any new model run, prepare a new config/run identity,
estimate task count and runtime, check the exact digest and sandbox, and obtain
explicit authorization for that bounded execution. Commercial release also
requires an affirmative rights decision by the authorized owner.

## Prepared command and resource envelope

The read-only `production plan` for
`configs/production/premium_qualification_80.yaml` passed on 2026-09-30.
It reported current config identity
`sha256:41655ffc848d54b4b420ddcba086fc77b6afef70bee0beb70dee17f68a38bf53`,
model digest `a2d26ea0b96b7a40afd673158d5cf44de25eff07fc8abf835e2cde5444632bc4`,
and expected sandbox digest
`sha256:6ee6badb20867c6426abb0b2ced747a126178f0a99b5bf4d94e65a62c236f7ac`.
Storage, configuration, and exact local model digest checks passed. Docker,
sandbox image availability, and template-diversity checks failed. The first authorized batch
would attempt 80 tasks and up to 240 model candidates. TQ-005's observed
262.5 minutes for 246 candidates suggests roughly four hours of generation
as a coarse planning scale, not a prediction for new tasks or the new settings.
The config caps total work at 320 tasks, 960 candidates, and 2,880 minutes,
with one batch per authorization.

The command after task diversity and a new smoke qualification are accepted is:

```powershell
factory production plan --config configs/production/premium_qualification_80.yaml
factory production preflight --config configs/production/premium_qualification_80.yaml
factory production run --config configs/production/premium_qualification_80.yaml --run runs/premium-qualification-080 --execute
```

The read-only plan reported catalog ID
`sha256:735d904cc6531a75d645ab442be464c8bb7d78cbbdb257fec2a7dbc60bdd5249`.
The prior 4.2 config identity, catalog ID, and preflight are stale. Current
preflight fails both the diversity gate and Docker/sandbox checks. No execution approval is
recorded. The planned 80-task batch should not run
with the current mostly single-question-per-family library; the matrix above
must first become validated templates, and a smaller diverse smoke must pass.
