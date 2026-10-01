# Golden dataset quality versus quantity

Research date: 2026-09-29. Scope: primary research papers, official
benchmark documentation, and measured artifacts from
`smoke-qualification-001`. Labels used below: **RESEARCH** (supported by
an external primary source), **MEASURED** (read directly from this repo's
artifacts), **INFERENCE** (a recommendation derived from those facts), and
**UNKNOWN** (requires an experiment or human judgment).

## Executive decision

The project should improve **quality and effective diversity before raw
quantity**, then scale only after the repaired pipeline passes a human
audit. This is not a claim that quantity is unimportant. It is a sequencing
decision:

1. fix known measurement and sampling defects;
2. regenerate a clean, diverse qualification set;
3. audit it;
4. scale the same accepted process;
5. measure downstream model lift.

For an **evaluation dataset**, incorrect or ambiguous items can invalidate
the score, so correctness has priority. For a **training dataset**, a small
clean set can be data-efficient, but it cannot provide broad schema,
language, and SQL-pattern coverage; after a quality floor is met, additional
*novel* examples are valuable. Repeating near-identical templates increases
row count without equivalent information gain.

The current smoke run is a useful pipeline qualification, but is insufficient
to demonstrate training utility or benchmark quality: it has 6 Golden records, all 10
families among the 30 candidates but only 6 families among Golden, 75%
construct coverage, 70.6% edge-case coverage, and a candidate-level semantic
duplicate rate of 100% (**MEASURED**). The code also flags 30/30 candidates
for internal exact task overlap among siblings; external benchmark overlap
was not measured. The present
10-record audit queue covers only 4 unique tasks because multiple sibling
candidates from the same task were selected (**MEASURED**). Human review is
therefore not the only remaining step.

## What the research actually supports

### Evidence for quality-first curation

- **Code-model training:** Microsoft's phi-1 work trained a 1.3B code model
  on 6B tokens selected as "textbook quality" plus 1B synthetic textbook and
  exercise tokens and reported 50.6% HumanEval and 55.5% MBPP pass@1. This
  demonstrates that carefully selected and synthetic code data can be highly
  data-efficient; it does not prove that 7B tokens are universally sufficient
  or that its results transfer directly to SQL
  ([Gunasekar et al., 2023](https://www.microsoft.com/en-us/research/publication/textbooks-are-all-you-need/)).
- **Instruction tuning:** LIMA reported strong instruction-following behavior
  after supervised fine-tuning a pretrained 65B model on 1,000 curated
  examples. Its main implication is that post-training quality can matter more
  than raw count once knowledge already exists in the base model. It is not a
  pretraining scaling result, and its broad chat evaluations are not SQL
  evaluations
  ([Zhou et al., 2023](https://arxiv.org/abs/2305.11206)).
- **Controlled corpus curation:** DataComp-LM tested filtering and mixing
  recipes under standardized training and evaluation. Its model-based filtered
  baseline reached comparable broad performance with substantially less
  compute than cited peers. This supports treating dataset design as an
  optimization problem rather than counting rows alone
  ([Li et al., 2024](https://arxiv.org/abs/2406.11794)).
- **Deduplication:** Google-led experiments found that deduplication reduced
  memorized emission and required fewer optimization steps to reach the same
  or better accuracy. The BigCode Stack experiments likewise reported that
  near-deduplication improved code-model performance across their experiments
  ([Lee et al., 2022](https://arxiv.org/abs/2107.06499),
  [Kocetkov et al., 2022](https://arxiv.org/abs/2211.15533)). This is directly
  relevant to the factory's sibling-candidate and template duplication.
- **Evaluation rigor:** EvalPlus expanded HumanEval with roughly 80 times more
  tests and fixed incorrect reference solutions, showing that a plausible
  solution passing thin tests need not be correct
  ([Liu et al., NeurIPS 2023](https://papers.neurips.cc/paper_files/paper/2023/hash/43e9d647ccd3e4b7b5baab53f0368686-Abstract-Conference.html)).
  **INFERENCE:** the factory's hidden, property, metamorphic, and mutation
  checks are an asset; discriminating coverage deserves priority over an
  unverified row count.
- **Human validation of coding evaluations:** SWE-bench Verified was created
  after professional developers reviewed samples for well-specified issues and
  appropriate tests. Each sample received three independent labels, and a
  conservative ensemble filtered the final 500 examples
  ([OpenAI, 2024](https://openai.com/index/introducing-swe-bench-verified/)).
  This is strong evidence that executable tests do not eliminate the need for
  human review of intent, ambiguity, and test adequacy.
- **SQL-specific label risk:** An ACL 2024 audit of BIRD found prevalent noise
  in natural-language questions and gold SQL and found that corrected SQL could
  materially change method comparisons
  ([Wretblad et al., 2024](https://aclanthology.org/2024.acl-short.34/)).
  Execution alone can also accept queries that happen to agree on one database;
  distilled multi-database test suites were proposed to approximate semantic
  accuracy more tightly
  ([Zhong et al., 2020](https://aclanthology.org/2020.emnlp-main.29/)).

### Evidence that quantity and breadth still matter

- **Pretraining:** Chinchilla's controlled scaling experiments found that
  model size and training tokens should rise together under a fixed compute
  budget. This is compelling evidence that more data matters for pretraining,
  but it does not specify the best size of a SQL supervised fine-tuning set
  ([Hoffmann et al., 2022](https://arxiv.org/abs/2203.15556)).
- **Code pretraining at scale:** StarCoder's official training dataset contains
  about 250B tokens after cleaning, decontamination, PII filtering, and
  near-deduplication. Its construction illustrates the combined strategy used
  in serious code corpora: scale *after* curation, not scale instead of
  curation
  ([BigCode StarCoderData card](https://huggingface.co/datasets/bigcode/starcoderdata)).
- **SQL generalization requires breadth:** Spider contains 10,181 questions and
  5,693 unique SQL queries over 200 databases in 138 domains, and separates
  databases between train and test to measure generalization to unseen schemas
  and programs. The important property is not just its row count; it is breadth
  across schemas, domains, language, and SQL structures
  ([Yu et al., 2018](https://aclanthology.org/D18-1425/)).
- **Realism adds information not supplied by templates:** KaggleDBQA was built
  from real web databases with original formatting, domain-specific types, and
  unrestricted questions because existing benchmark performance did not fully
  represent real-world transfer
  ([Lee et al., 2021](https://aclanthology.org/2021.acl-long.176/)).

**INFERENCE:** the project should prioritize **quality x diversity x quantity**, in that order
for this project. Quality determines whether a row is trustworthy; diversity
determines whether another row adds information; quantity determines coverage
and statistical power after the first two conditions hold.

## Current run: evidence-based diagnosis

Source:
`runs/smoke-qualification-001/quality/export/dataset_health.json`,
`runs/smoke-qualification-001/reports/production-report.json`, and
`runs/smoke-qualification-001/quality/export/audit_sample.jsonl`.

| Dimension | Current evidence | Interpretation |
|---|---:|---|
| Generation | 30/30 candidates generated | Generator/API path is operational. |
| Automated verification | 24/30 PASS; 6/30 Golden | Strong filtering is working, but Golden quantity is only a demonstration. |
| Verification strength | 80% strong; mutation mean 1.0 on scored records | Good signal, limited by the small and homogeneous sample. |
| Reliability | 1 execution failure; 2 result mismatches; 3 inconclusive | Known failures remain, concentrated in Funnel and Subqueries. |
| Family breadth | 10/10 candidate families; 6/10 Golden families | Candidate coverage is good; releasable coverage is incomplete. |
| Construct breadth | 12/16 constructs (75%) | HAVING, DISTINCT, UNION, and LIMIT are absent. |
| Edge breadth | 12/17 edges (70.6%) | Five declared edge classes remain absent. |
| Duplicate signal | exact 46.7%; structural 50%; semantic 100% | At least part of this is sibling candidates sharing one task. It must be separated from release-level duplication before it can guide a go/no-go decision. |
| Contamination signal | 30/30 `EXACT_OVERLAP`; split overlap 0 | The implementation flags identical task text across sibling candidates. This is not evidence of external benchmark contamination; it is a metric-scope problem. |
| Audit queue | 10 records, 4 unique tasks | It is not representative of all 10 families and spends reviewer time on siblings. |
| Human audit | 0 completed | Correctness and naturalness claims remain unvalidated. |
| Empirical difficulty | unavailable | One attempt per record cannot establish a solve-rate difficulty distribution. |

Important distinction: three candidates for one task are useful during
generation and selection, but they are not three independent natural-language
training problems. Candidate-level redundancy should be reported separately
from release-record diversity. Similarly, the current `EXACT_OVERLAP` flags do
not establish contamination against an external corpus or a private evaluation
split.

## Work that should happen before human review

These steps prevent paying reviewers to rediscover known mechanical problems.

1. **Correct the unit of duplicate and contamination reporting.** Report
   sibling candidates as generation redundancy. Compute release duplication on
   selected records and reserve "contamination" for train/eval, known-source,
   or external-overlap evidence. Keep both metrics; do not merely hide the
   candidate duplication.
2. **Repair the audit sampler.** For this six-record smoke set, review every
   Golden record. Add one representative per remaining family/failure mode,
   with no duplicate sibling candidates unless candidate comparison is the
   stated audit purpose. The audit manifest must state its population,
   inclusion rules, strata, seed, and inclusion probabilities when random
   sampling is used.
3. **Investigate the concentrated failures first.** Funnel has 3/3 FAIL;
   Subqueries has 3/3 INCONCLUSIVE in this one-task-per-family smoke run.
   Diagnose whether each failure belongs to the candidate, task contract,
   fixture, or verifier before changing anything. Version any necessary repair,
   preserve the smoke evidence, and rerun under a new immutable run identity.
4. **Exercise the missing constructs and edge cases.** Add targeted tasks for
   HAVING, DISTINCT, UNION, LIMIT, empty results, negative values, retention
   boundaries, same-timestamp steps, and window-end boundaries. These should
   be verified before being added to a human queue.
5. **Freeze review inputs.** Pin the exact task, schema, fixtures, candidate
   SQL, verifier evidence, model revision, and hashes. A review decision must
   continue to point to the exact bytes that were reviewed.
6. **Finalize the audit rubric and adjudication path.** Reviewers need explicit
   checks for NL intent, ambiguity, schema consistency, SQL semantics, expected
   result, edge coverage, and naturalness. A diagnostic sample can be reviewed
   separately. Every proposed release row requires two blind independent
   decisions, third-reviewer adjudication of each disagreement, and final
   PASS. Report agreement as well as initial pass rate.
7. **Keep legal/governance gating visible.** The smoke config labels the current
    checkpoint `REVIEW_REQUIRED_NON_COMMERCIAL`. Better data does not resolve
    model-output licensing or commercial-clearance questions.
    Production-002 is prepared but unauthorized; this recommendation does not
    authorize its execution. The small pre-scale audit proposed here is an
    intermediate qualification gate, not a replacement for the master plan's
    final release audit.

### Review workflow gap and score interpretation

**MEASURED (code inspection):** `src/verified_data_factory/cli_quality.py`'s
`audit` command recomputes the sample from input records each invocation,
updates one candidate in memory, and writes a new JSON payload. It does not
reload earlier decisions. `src/verified_data_factory/production/runner.py`
calls `analyze_dataset(records, quality_config)` without audit overrides, so
these CLI decisions do not flow into the existing run's exported quality
selection. `quality/aggregation.py` does support an in-memory map of audit
overrides, but that is not a durable two-blind-reviewer/adjudication workflow.
Build a versioned, append-only review decision artifact bound to frozen record
hashes, with independent reviewer identities, disagreement resolution, and a
new derived release candidate; never edit the original smoke run in place.

**INFERENCE (existing house rubric):** `docs/remediation-result.md` scores the
46-row `controlled-requalification-002` commercial product at **52/100**;
`docs/research-roadmap-90.md` keeps that score until independent review,
rights, replay, and utility evidence exist. It is not a statistical accuracy
measure, a score for all historical runs, or a public standard. The separate
older **62/100** score in
`docs/research/enterprise-sql-dataset-quality-scorecard.md` uses a different
rubric and an earlier Production-001 snapshot; these numbers are not a trend.
The smoke run improves *pipeline qualification evidence*, but is a paused,
non-commercial 6-Golden run and does not establish that the buyer score rose.

After those steps, human review is the correct next gate. Human review should
not be postponed until a large production run: that would multiply any hidden
task-language, oracle, and sampling defect.

## What to improve after the first audit passes

### Improve quality

- Require zero unresolved execution, oracle, and verifier defects in accepted
  Golden records.
- Measure verifier adequacy with mutation kills and counterexample fixtures,
  not only execution success.
- Add independent review of instruction meaning and naturalness; synthetic
  instructions can be logically precise but unnaturally prescriptive.
- Validate a sample on a second SQL engine before making portability claims.
- Separate public training fields from private verifier fixtures and answers.
- Maintain source/model/license lineage per record and clear the generator
  checkpoint before commercial distribution.

### Improve useful quantity

- Scale unique tasks and schemas, not candidate siblings.
- Set quotas for underrepresented Golden families and SQL constructs.
- Vary schema topology, names, types, cardinalities, null patterns, temporal
  boundaries, and natural-language paraphrases.
- Hold out entire schemas/templates for evaluation, following Spider's
  cross-database principle.
- Track marginal novelty per batch. Pause when new records mostly join existing
  structural or semantic duplicate groups.

### Prove that either improvement matters

No cited paper can supply the factory's expected downstream lift
(**UNKNOWN**). Run a controlled ablation after enough accepted records exist:

- **A:** small, verified, diversity-balanced set;
- **B:** a larger set sampled from the same verified process;
- **C:** a size-matched set without the strongest quality filters;
- **D:** the base model with no fine-tuning.

Keep the base checkpoint, optimizer, token exposure, and evaluation harness
fixed. Evaluate on private, schema-disjoint tasks with strong test suites.
Report confidence intervals and per-family results, not only a blended score.
The A-vs-C comparison estimates the value of quality; A-vs-B estimates the
marginal value of quantity after quality control. Until this experiment is
run, claims that the dataset improves a model remain unsupported.

## Practical targets

These are **house gates**, not public standards:

- **Before human audit:** corrected candidate/release metrics; a sampler that
  covers all six Golden records and all remaining families/failure modes;
  Funnel and Subquery root causes resolved; a fresh immutable smoke run.
- **Before a controlled larger batch:** use diagnostic review findings to
  decide whether to continue, report reviewer agreement, resolve any
  disagreements, investigate hard contamination flags, and seek 10/10 Golden
  family coverage in the qualification set. A 90% diagnostic pass rate is not
  a release gate. Every accepted release row must ultimately have final PASS.
- **Before calling it training data:** materially more unique task-language
  pairs and schemas, explicit held-out schemas, a training-safe field export,
  and a measured fine-tuning experiment.
- **Before calling it a benchmark:** enough independently reviewed items for
  per-family reporting, private test fixtures, leakage controls, and evidence
  that small changes in a few items do not dominate rankings.

There is no defensible universal target such as "1,000 Goldens is enough."
The target depends on whether the product is a training set, private benchmark,
or verifier dataset; the intended model size; and the measured learning curve.
The next rational investment is therefore not maximum generation volume. It is
fixing the measurement/sampling issues, auditing a clean qualification set,
and then buying scale only where each new record increases coverage or model
performance.

## Primary sources

- Gunasekar et al., *Textbooks Are All You Need* (2023):
  https://www.microsoft.com/en-us/research/publication/textbooks-are-all-you-need/
- Zhou et al., *LIMA: Less Is More for Alignment* (2023):
  https://arxiv.org/abs/2305.11206
- Li et al., *DataComp-LM* (2024): https://arxiv.org/abs/2406.11794
- Hoffmann et al., *Training Compute-Optimal Large Language Models* (2022):
  https://arxiv.org/abs/2203.15556
- Lee et al., *Deduplicating Training Data Makes Language Models Better*
  (2022): https://arxiv.org/abs/2107.06499
- Kocetkov et al., *The Stack* (2022): https://arxiv.org/abs/2211.15533
- BigCode, official StarCoderData dataset card:
  https://huggingface.co/datasets/bigcode/starcoderdata
- Liu et al., *Is Your Code Generated by ChatGPT Really Correct?* (NeurIPS
  2023):
  https://papers.neurips.cc/paper_files/paper/2023/hash/43e9d647ccd3e4b7b5baab53f0368686-Abstract-Conference.html
- OpenAI, *Introducing SWE-bench Verified* (2024):
  https://openai.com/index/introducing-swe-bench-verified/
- Yu et al., *Spider* (EMNLP 2018): https://aclanthology.org/D18-1425/
- Wretblad et al., *Understanding the Effects of Noise in Text-to-SQL* (ACL
  2024): https://aclanthology.org/2024.acl-short.34/
- Zhong et al., *Semantic Evaluation for Text-to-SQL with Distilled Test
  Suites* (EMNLP 2020): https://aclanthology.org/2020.emnlp-main.29/
- Lee et al., *KaggleDBQA* (ACL 2021):
  https://aclanthology.org/2021.acl-long.176/

## Caveats

The cited studies use different models, compute budgets, tasks, and evaluation
methods. Results from pretraining, general instruction tuning, Python code, and
SQL evaluation are not interchangeable. They support the direction of the
recommendation, not a precise row-count threshold or a promised performance
gain for this project. The repo's current measurements come from one 10-task
smoke run and are too small for stable rate estimates.
