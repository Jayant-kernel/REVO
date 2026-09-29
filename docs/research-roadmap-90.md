# Evidence-based roadmap from 52/100 to above 90

## Decision summary

**INFERRED** — The shortest defensible route is a release of **70–80 records**
that covers all ten planned SQL families, is independently reviewed row by row,
has a signed commercial-rights packet, reproduces in a clean second environment,
and produces a pre-registered improvement on a held-out buyer-relevant evaluation.
Passing the existing automated checks alone cannot raise the buyer-oriented score
above 90.

**INFERRED** — A realistic target after all gates below pass is **93/100**, with
roughly three points of scoring uncertainty. The number is an assessment under the
existing local rubric, not a certification. Any unresolved release right, failed
independent review, or absent utility result keeps the release below 90 regardless
of the arithmetic.

## 1. Verified starting point

**MEASURED** — `runs/controlled-requalification-002/quality/export/dataset_health.json`
reports 46 Golden rows, a 1.0 strong-verification rate, a 1.0 mean mutation score,
zero exact, semantic, and structural duplicate rates, and zero split overlaps.

**MEASURED** — The same health report shows only 2/10 families, 10/16 SQL
constructs, and 3/17 edge-case categories. The uncovered families are simple
joins, multi joins, aggregation, subqueries, window functions, deduplication,
retention, and funnel.

**MEASURED** — Direct parsing of the 46-line Golden JSONL found two template IDs,
two schema payloads, and two distinct instruction strings: 18 CTE rows and 28
temporal rows. Method: parse every JSONL row and count canonical instruction,
schema, family, and template values.

**MEASURED** — Six of 57 analyzed candidates carry `EXACT_OVERLAP` flags, while
the recorded split-overlap count is zero. The local report explains these as soft
sibling/task-overlap flags; it does not establish overlap with external public
benchmarks.

**MEASURED** — Eleven records remain `AUDIT_PENDING`; the 46 released Golden rows
have no completed independent human-review evidence.

**FACT** — `docs/remediation-result.md` records complete provenance chains for all
46 rows, 160/160 resolvable bundled artifact references, and zero provenance graph
problems.

**MEASURED** — The bundle's `reproducibility.json` marks every row's overall
status `CONDITIONAL` because generation is reconstructable from preserved response
artifacts but is not guaranteed bit for bit. The same file marks task, execution,
verification, quality, and dataset reproduction `VERIFIED`.

**FACT** — `docs/remediation-result.md` states that no release-specific commercial
rights packet and no buyer utility experiment have been supplied.

**UNKNOWN** — The exact checkpoint license, the legal status of the named
`huihui-devstral-small-2-24b-instruct-2512-abliterated-latest` derivative, its
upstream obligations, and the right to redistribute its generated outputs have
not been established by the inspected release evidence.

## 2. Why the remaining work is necessary

### Dataset documentation

**FACT (external)** — *Datasheets for Datasets* proposes documenting motivation,
composition, collection, preprocessing, uses, distribution, and maintenance so a
consumer can judge fitness for use ([Gebru et al., CACM 2021](https://doi.org/10.1145/3458723)).
Google's Data Cards work likewise treats dataset documentation as a user-facing
product and calls for upstream sources, collection and annotation methods,
evaluation, intended use, and performance-shaping decisions
([Pushkarna et al.](https://arxiv.org/abs/2204.01075)).

**FACT (external)** — MLCommons Croissant 1.1 provides versioned, machine-readable
dataset metadata, including description, license, distributions, record sets,
fields, and descriptive statistics. It also shows how to attach W3C PROV terms
([Croissant 1.1 specification](https://docs.mlcommons.org/croissant/docs/croissant-spec-1.1.html)).

**INFERRED** — The present remediation report is engineering evidence, but it is
not yet a buyer-ready datasheet, field dictionary, maintenance policy, or
machine-readable dataset card. A public release needs both readable and
machine-readable documentation.

### Provenance and reproducibility

**FACT (external)** — W3C PROV defines interoperable `Entity`, `Activity`, and
`Agent` concepts and relations including generation, derivation, attribution,
usage, association, and collection membership
([W3C PROV-O Recommendation](https://www.w3.org/TR/prov-o/)).

**FACT (external)** — ACM SIGMOD's reproducibility process distinguishes artifact
availability from independent reproduction: an outside database group reruns the
core results and records a report
([SIGMOD Availability and Reproducibility Initiative](https://reproducibility.sigmodconf.hosting.acm.org/)).

**INFERRED** — Resolvable hashes prove bundle integrity, while a clean-room replay
by someone outside the implementation team is needed to demonstrate operational
reproducibility. Model nondeterminism does not require byte-identical new model
answers; the frozen release itself must reproduce exactly, and rerunning its
verification must reproduce all verdicts and metrics.

### Independent human review

**FACT (external)** — NIST AI RMF 1.0 states that rigorous assessment should include
uncertainty, benchmark comparisons, formal reporting, and objective and repeatable
TEVV. Measure 1.3 calls for internal experts who were not front-line developers
and/or independent assessors; Measure 2.3 calls for performance under conditions
similar to deployment
([NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)).

**FACT (external)** — NIST's statistical handbook recommends that sampling plans
represent the parameters of interest and that sample sizes be chosen from the
required confidence and precision. It warns that normal approximations can be
inaccurate when samples or defect counts are small and supplies exact binomial
intervals
([sampling plans](https://www.itl.nist.gov/div898/handbook/ppc/section3/ppc33.htm),
[exact binomial intervals](https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm)).

**INFERRED** — With at most 80 records, sampling saves little and weakens the
claim. Review 100% of release rows independently. Two SQL reviewers should judge
the instruction, schema, expected semantics, boundary behavior, answer SQL, and
fixture discrimination before seeing one another's decisions. A third reviewer
should adjudicate every disagreement. Report raw agreement and disagreement by
family; do not substitute an agreement statistic for adjudication.

### SQL diversity, semantics, and realism

**FACT (external)** — Spider contains 10,181 questions and 5,693 unique complex SQL
queries on 200 databases in 138 domains, and uses a database split to test
generalization to unseen schemas
([Spider, EMNLP 2018](https://aclanthology.org/D18-1425/)).

**FACT (external)** — BIRD was designed to narrow the realism gap left by small
academic databases. It includes 12,751 text-to-SQL pairs across 95 databases and
37 professional domains, totaling 33.4 GB, and tests dirty values, external
knowledge, and SQL efficiency
([BIRD, NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/hash/83fc8fab1710363050bbd1d4b8cc0021-Abstract-Datasets_and_Benchmarks.html)).

**FACT (external)** — Spider 2.0 uses 632 enterprise workflow problems, databases
that often exceed 1,000 columns, BigQuery, Snowflake, and SQLite, and workflows
that may require multiple queries and more than 100 lines
([Spider 2.0 official site](https://spider2-sql.github.io/)).

**FACT (external)** — Execution on one fixture can misclassify SQL semantics.
Distilled test-suite accuracy evaluates candidate queries on multiple generated
databases chosen for code coverage; its authors found the prior Spider metric had
an average 2.5% false-negative rate and up to 8.1% in their comparison
([Zhong, Yu, and Klein, EMNLP 2020](https://aclanthology.org/2020.emnlp-main.29/)).

**INFERRED** — This release need not match the scale of Spider or BIRD to be a
valuable compact Golden set. It does need more than repeated seeds of two task
templates. A buyer should see independent schemas, natural instruction forms,
multiple semantic families, realistic value distributions, and discriminating
test databases.

### Split isolation and contamination

**FACT (external)** — Research on text-to-SQL evaluation found that common random
splits mainly test paraphrase robustness and only partly test generalization to new
queries; it recommends complementary splits by SQL query structure
([Finegan-Dollak et al., ACL 2018](https://aclanthology.org/P18-1033/)). Spider's
database split separately tests unseen-schema generalization.

**FACT (external)** — Spider 2.0 explicitly warns against using released Gold SQL
for supervised fine-tuning because doing so can compromise evaluation fairness
([Spider 2.0 official site](https://spider2-sql.github.io/)).

**INFERRED** — Candidate-level random splitting is insufficient when siblings
share a task, schema, template, or normalized SQL shape. Isolation must occur at
the schema and task-template lineage level, and evaluation gold must be kept out
of all training products.

### Licensing and commercial rights

**FACT (external)** — SPDX is ISO/IEC 5962:2021 and supplies standardized,
machine-readable license identifiers and expressions, including `AND`, `OR`, and
`WITH`
([SPDX specifications](https://spdx.dev/use/specifications/),
[SPDX license expressions](https://spdx.dev/learn/handling-license-info/)).

**FACT (external)** — CC BY 4.0 permits sharing and adaptation, including
commercially, subject to attribution and change notices. Creative Commons also
warns that the license may not cover other necessary rights
([CC BY 4.0 official deed](https://creativecommons.org/licenses/by/4.0/)).

**INFERRED** — Choosing a dataset license is the last rights step. Before that,
the owner must establish the rights for every template, prompt, fixture source,
model/checkpoint, upstream fine-tune, generated output, and bundled dependency.
A model card or repository tag without an immutable revision and the applicable
license text is not adequate evidence.

### Utility evidence and release governance

**FACT (external)** — NIST AI RMF calls for documented test sets, metrics, tools,
uncertainty, benchmark comparisons, independent assessment, deployment-similar
conditions, and continuing measurement. These requirements support a controlled
buyer utility study rather than an anecdotal before/after result
([NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)).

**FACT (external)** — Croissant exposes versioned conformance, license,
distribution, record/field descriptions, and statistics, which can form the
machine-readable part of a release contract
([Croissant 1.1 specification](https://docs.mlcommons.org/croissant/docs/croissant-spec-1.1.html)).

## 3. Acceptance gates for a score above 90

The thresholds below are **INFERRED** buyer-readiness thresholds. They should be
frozen before generation or review so the release is not graded after seeing its
results.

### Gate A — Breadth and independent coverage

1. **INFERRED requirement** — Ship 70–80 accepted rows, with at least six accepted
   rows in each of all ten planned families and no family above 20% of the release.
2. **INFERRED requirement** — Cover all 16 tracked constructs and at least 15/17
   tracked edge-case categories. Any uncovered category must have a written scope
   reason.
3. **INFERRED requirement** — Include at least ten independently designed schema
   fingerprints across at least five business domains. No schema may contribute
   more than 15% of rows.
4. **INFERRED requirement** — Use at least 40 materially distinct instruction
   phrasings in an 80-row release. Reviewers must reject recipe-like instructions
   that reveal the query plan instead of describing a business question.
5. **INFERRED requirement** — Exercise at least two materially different SQL
   dialects with dialect-specific execution. If the commercial scope remains
   DuckDB-only, document that limitation and expect the realism score to remain
   below its maximum.

### Gate B — Semantic and verification assurance

1. **INFERRED requirement** — Every row passes syntax, execution, independent
   oracle comparison, properties, metamorphic checks, and valid-mutant testing.
   Invalid mutants remain excluded from mutation-score credit.
2. **INFERRED requirement** — Each row is tested on at least three discriminating
   fixture instances: a normal case, declared edge cases, and an independently
   authored adversarial case. The exact number may grow until every known wrong
   query is distinguished.
3. **INFERRED requirement** — Add counterexamples for NULL three-valued logic,
   duplicate and tie behavior, empty groups/results, join multiplicity, missing
   relationships, zero/negative values, temporal boundaries, timestamp ties,
   and deterministic ordering wherever applicable.
4. **INFERRED requirement** — Obtain zero unresolved semantic defects after human
   adjudication. A discovered systemic defect triggers regeneration and re-review
   of every affected family, not a one-row patch.

### Gate C — Full independent human adjudication

1. **INFERRED requirement** — Two reviewers independently inspect 100% of the
   final rows, with reviewer identity, rubric version, timestamps, decision, and
   reason recorded.
2. **INFERRED requirement** — A third SQL expert resolves every disagreement.
   Release only rows with an adjudicated `PASS` and no open severity-1 or
   severity-2 issue.
3. **INFERRED requirement** — Review the current 11 `AUDIT_PENDING` rows; either
   correct and re-verify them or exclude them. Their automated pass is not human
   approval.
4. **INFERRED requirement** — Report initial agreement, disagreement categories,
   final defect counts, fixes, and post-fix re-review. Keep reviewer instructions
   and examples in the release evidence.

### Gate D — Realism and empirical difficulty

1. **INFERRED requirement** — Replace tiny uniform fixtures with synthetic or
   cleared workloads containing realistic cardinality, skew, NULLs, duplication,
   messy categorical values, sparse relationships, time zones, and date/time
   boundaries. Do not copy benchmark data into training rows.
2. **INFERRED requirement** — Include multi-table business schemas and tasks that
   require joins, nested queries, windows, cohort/retention logic, funnels,
   deduplication, and performance-aware alternatives.
3. **INFERRED requirement** — Measure difficulty empirically using a frozen panel
   of at least three model capability levels and at least three attempts per row.
   Publish solve rates by family and retain a mix of easy, medium, hard, and
   unsolved-by-baseline rows. Declared difficulty alone does not pass this gate.
4. **INFERRED requirement** — Report runtime and resource distributions and reject
   pathological answers that are semantically correct but commercially unusable
   under the stated execution budget.

### Gate E — Split isolation and external contamination search

1. **INFERRED requirement** — Assign train, development, and test roles by whole
   schema/database first, then by template/query lineage. All siblings and
   paraphrases remain in one split.
2. **INFERRED requirement** — Require zero exact record, normalized SQL AST, schema
   fingerprint, or task-template lineage overlap between splits. Manually
   adjudicate semantic and natural-language near matches.
3. **INFERRED requirement** — Fingerprint against legally obtained copies of
   Spider, BIRD, WikiSQL, Spider 2.0, and every internal corpus used by the buyer.
   Report corpus version/hash, matching methods, thresholds, match counts, and
   dispositions. Do not claim universal absence of contamination; state which
   corpora and match classes were checked.
4. **INFERRED requirement** — Keep final evaluation answers access-controlled and
   out of training exports, prompt examples, logs, and model-selection feedback.

### Gate F — Commercial-rights packet

1. **INFERRED requirement** — Produce a component ledger for the dataset rows,
   schemas, templates, prompts, generator checkpoint, base model, fine-tunes,
   libraries, and any source material. Record owner, immutable version/digest,
   source URL, license text/hash, SPDX expression where applicable, attribution,
   restrictions, and intended commercial use.
2. **INFERRED requirement** — Resolve the exact license chain for the named
   `huihui`/Devstral derivative and its upstream model. If redistribution rights
   or output rights remain unclear, regenerate with a cleared model or keep the
   release internal.
3. **INFERRED requirement** — Have qualified counsel or an authorized internal
   rights owner sign a release-specific clearance statement. Engineering cannot
   infer commercial permission from technical availability.
4. **INFERRED requirement** — Select the outgoing dataset license only after the
   chain is cleared; bundle the license, notices, attributions, warranty statement,
   and acceptable-use or contractual terms actually intended for customers.

### Gate G — Independent reproduction

1. **INFERRED requirement** — Freeze a release candidate with content hashes,
   dependency lock, container digest, seeds, configs, templates, oracles, and
   verifier versions.
2. **INFERRED requirement** — Give the bundle and written runbook to a person who
   did not implement the pipeline. In a clean second environment, they must
   reconstruct the export byte for byte from preserved artifacts and reproduce
   100% of verification decisions and health metrics.
3. **INFERRED requirement** — Record machine/OS/runtime details, commands, timing,
   deviations, failures, and the independent reviewer's signed outcome. A failed
   replay blocks release until fixed and rerun.

### Gate H — Buyer utility experiment

1. **INFERRED requirement** — Pre-register the baseline model, training recipe,
   random seeds, compute budget, untouched evaluation sets, primary metric,
   subgroup metrics, confidence-interval method, minimum useful effect, and
   stopping rule.
2. **INFERRED requirement** — Compare at least: base model with no added data,
   base model plus the current 46-row set, base model plus the expanded set, and a
   size-matched control. Hold every factor except dataset treatment constant.
3. **INFERRED requirement** — Evaluate on a sealed, fingerprint-clean,
   buyer-relevant set with unseen schemas. Report execution accuracy and
   multi-fixture test-suite accuracy overall and by family, schema, difficulty,
   and dialect.
4. **INFERRED requirement** — Use at least three training seeds and report paired
   uncertainty intervals. Recommended pass condition: the expanded set's 95%
   interval for improvement excludes zero on the pre-registered primary metric,
   meets a buyer-approved minimum useful effect, and has no material regression
   in a critical family.
5. **INFERRED requirement** — Preserve all run artifacts and publish null or
   negative results. A statistically positive result on a contaminated or reused
   tuning set does not pass.

### Gate I — Documentation and release governance

1. **INFERRED requirement** — Publish a datasheet covering motivation,
   composition, generation/collection, annotation, preprocessing, uses,
   out-of-scope uses, limitations, distribution, maintenance, and retirement.
2. **INFERRED requirement** — Publish Croissant 1.1 JSON-LD with license,
   distributions, checksums, record sets, field-level semantics, types, and
   descriptive statistics. Link its provenance fields to the existing bundle.
3. **INFERRED requirement** — Provide a schema/data dictionary, example loader,
   evaluation protocol, quality report, human-review report, contamination report,
   rights packet, independent replay report, utility report, and changelog.
4. **INFERRED requirement** — Use immutable semantic versions. A release committee
   consisting of engineering, an independent SQL reviewer, legal/rights, and a
   product owner must sign the frozen candidate. Document withdrawal, correction,
   deprecation, incident response, buyer notification, and maintenance ownership.
5. **INFERRED requirement** — Never edit a published release in place. Corrections
   create a new version with a machine-readable row-level change map and retained
   prior hashes.

## 4. Ordered execution plan

### Phase 1 — Define the product and freeze the gates

**INFERRED** — Write the intended buyer/use case, supported dialects, target size,
prohibited uses, acceptance rubric, utility metric, and rights policy first. This
prevents later generation from redefining success around whatever passed.

**Deliverables:** signed scope; frozen score rubric; reviewer guide; preregistered
coverage matrix; preregistered utility plan.

### Phase 2 — Clear rights before expensive generation

**INFERRED** — Resolve the current checkpoint and upstream chain immediately. If
it cannot be cleared, choose a generator with explicit commercial terms before
creating more records. Build the component ledger and have the intended release
license reviewed.

**Exit:** signed rights packet with no `UNKNOWN` or incompatible component.

### Phase 3 — Design coverage, schemas, and evaluation isolation

**INFERRED** — Allocate 70–80 slots across all ten families, independent schemas,
domains, constructs, edges, difficulty bands, and dialects. Freeze entire unseen
schemas for evaluation before generation. Build external fingerprints before
acceptance so contaminated rows never enter a release pool.

**Exit:** all Gate A targets are reachable on paper; split lineages are disjoint.

### Phase 4 — Generate, verify, and adversarially test

**INFERRED** — Generate multiple candidates, but select rows for semantic and
instruction diversity rather than seed count. Verify each on independently
authored multi-fixture test suites. Track valid kills, survivors, invalid mutants,
and infrastructure failures separately.

**Exit:** 70–80 records pass Gate B; health output covers all ten families.

### Phase 5 — Independent human review and repair loop

**INFERRED** — Run blind dual review on every proposed row. Adjudicate all
disagreements. When a systemic defect appears, repair the generating contract or
oracle and re-review the complete affected stratum.

**Exit:** every shipped row has two decisions plus adjudication where needed; no
open semantic defect remains.

### Phase 6 — Reproduce and test utility

**INFERRED** — Freeze the candidate, run an independent clean-environment replay,
then execute the preregistered multi-seed buyer utility experiment. Do not alter
the dataset after seeing evaluation results without declaring a new candidate and
repeating the test on a fresh sealed set.

**Exit:** Gate G and Gate H pass with complete reports.

### Phase 7 — Package and approve the release

**INFERRED** — Produce the datasheet, Croissant metadata, license/notices,
coverage and quality reports, contamination report, audit report, replay report,
utility report, checksums, changelog, and support/withdrawal policy. Obtain all
four release approvals.

**Exit:** immutable versioned artifact with an approval record and publication
date.

## 5. Score projection tied to evidence

| Dimension | Weight | Current | Target | Evidence required for target |
|---|---:|---:|---:|---|
| Semantic correctness assurance | 15 | 13 | 15 | Full independent dual review; adjudicated zero unresolved defects; multi-fixture semantic tests |
| Verification discrimination | 15 | 13 | 15 | All ten families; independent adversarial fixtures; valid-mutant accounting; replayed results |
| Instruction quality and task independence | 10 | 6 | 9 | At least 40 materially distinct business instructions; recipe leakage rejected; reviewer approval |
| Diversity and independent coverage | 15 | 2 | 14 | 70–80 rows; 10/10 families; 16/16 constructs; at least 15/17 edge cases; schema/domain caps |
| Realism and demonstrated difficulty | 10 | 2 | 7 | Realistic workloads; multiple dialects; empirical multi-model solve rates and runtime results |
| Human review and adjudication | 10 | 1 | 10 | 100% blind dual review and independent adjudication evidence |
| Identity, provenance, reproducibility | 10 | 9 | 10 | Successful clean-environment independent replay and signed report |
| Separation and contamination assurance | 5 | 4 | 4 | Schema/lineage split isolation and versioned external fingerprint report |
| Rights and commercial clearance | 5 | 0 | 5 | Complete component ledger and signed release-specific clearance |
| Documentation and demonstrated utility | 5 | 2 | 4 | Datasheet, Croissant, governance package, and positive preregistered utility study |
| **Total** | **100** | **52** | **93** | **All binary release gates pass** |

**INFERRED** — The projected 93 is intentionally below 100. The remaining seven
points reflect a compact 70–80-row product, residual limits in enterprise realism,
the impossibility of proving absence of contamination against unknown corpora,
and uncertainty about generalization beyond the tested buyer setting.

**INFERRED** — A 90+ claim is defensible only after the evidence exists. Before
human adjudication, rights clearance, independent replay, and utility testing,
the score should remain 52 even if more rows are generated.

## 6. Stop conditions

**INFERRED** — Stop public/commercial release if any of these remains true:

- exact generator or upstream model rights are unknown;
- any release row lacks independent semantic approval;
- any schema, normalized SQL shape, task lineage, or sibling crosses train/test;
- an exact external benchmark match is unexplained;
- the independent replay changes a verdict, record hash, or reported metric;
- the utility study uses a tuned-on, contaminated, or non-buyer-relevant test set;
- the expanded dataset fails its preregistered useful-effect threshold;
- documentation omits intended use, limitations, maintenance owner, or correction
  process.

## 7. Where this roadmap may be too generous

**INFERRED** — A target of 14/15 for diversity may be generous for only 70–80
records. Evidence that would lower it is high within-family structural similarity
or poor results on unseen schemas. Evidence that would support it is low
concentration across schema, template, normalized AST, instruction, and domain
clusters plus utility gains on unseen schemas.

**INFERRED** — A target of 7/10 for realism may be generous if fixtures remain
small synthetic retail tables. It requires realistic scale/value distributions,
multiple domains and dialects, empirical difficulty, and buyer-relevant tasks.
Actual cleared customer-shaped schemas and workflows would justify a higher score.

**INFERRED** — A positive fine-tuning result may overstate value if the chosen
model already knows the public benchmark or if 70–80 examples produce unstable
effects. The size-matched control, unseen schemas, multiple seeds, contamination
scan, subgroup reporting, and confidence intervals are required to reduce this
risk.

**UNKNOWN** — Whether a buyer will accept 70–80 rows as a sellable standalone
dataset depends on the use case, exclusivity, support, benchmark secrecy, and
observed utility. Buyer interviews or a paid pilot could overturn the assumed
commercial value even if every technical gate passes.

**UNKNOWN** — Legal clearance cannot be predicted from repository metadata. A
qualified decision maker may find the current model chain unsuitable, requiring
regeneration and another full verification/review cycle.

**INFERRED** — With ten times more review time, the highest-value additional work
would be: independent manual reconstruction of every oracle contract; red-team
queries designed by external analytics engineers; a second utility study on a
different model family; a paid buyer pilot; and contamination comparison against
the buyer's private training and evaluation inventories.
