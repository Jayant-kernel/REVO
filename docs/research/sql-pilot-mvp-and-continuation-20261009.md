# SQL pilot MVP and continuation research

Checked 9 October 2026. This note is a product recommendation based on repository
evidence and primary public sources. Proposed pilot quantities are house targets,
not research-derived guarantees, market standards, or changes to engineering-1.0.

## Verified local baseline

The v17 catalog reports 57 contracts: 5 FULLY_VERIFIED and 52 QUARANTINED across
four qualified families. All 251 source hashes listed in that catalog matched the
working tree during this inspection. The retained full-regression receipt reports
exit zero and matching launch/post identities; the handoff records 1,487 passes,
seven report-format warnings, and no failures/skips/deselections. No Python process
was returned by the process snapshot during this inspection.

The remaining queue is 36 named-oracle engineering profiles and 16 semantic or
forward-schema cases. The accepted forward 80-record dataset is empty. Engineering
score is NOT_COMPUTABLE. The transient SLA backend early abort remains unexplained;
later successful tests establish subsequent success, not its cause. Current work
is local on main at 22ecfeb with extensive modified and untracked material.

Authorities: `scratch/funnel_experiment/engineering/catalog-two-families-v17.json`,
`checkpoint-two-families-v17-summary.json` in the same directory, and
`docs/production/engineering-program-handoff-20261008.md`.

The previous 50-60% completion and multiweek duration estimates were planning
judgments. There is no measured remaining-effort model supporting an exact 80%
completion target. Contract coverage, software test counts, pilot acceptance, and
engineering score must remain separate measurements.

## Public offerings and competitive context

These are current public offerings, not claims about vendors' original MVPs,
private procurement criteria, prices, or verified willingness to buy Revo data.

| Organization / artifact | First-party evidence | Implication for Revo |
|---|---|---|
| Gretel synthetic Text-to-SQL | The dataset card lists 105,851 records and 100 domains, with database context and several SQL complexity levels. [Dataset card](https://huggingface.co/datasets/gretelai/synthetic_text_to_sql) | A small general SQL corpus cannot differentiate through raw volume. The opportunity must be narrower and demonstrate additional value. |
| Scale Data Engine | Offers data generation, expert labeling, evaluation, and curation around model failures. [Product](https://scale.com/data-engine) | Buyers can obtain a service and an improvement cycle, not merely a JSONL file. Revo should offer reproducible evaluation and targeted diagnosis. |
| Surge AI | Advertises off-the-shelf training data, evaluations, and RL environments with vendor-reported benchmark improvements. [Offering](https://surgehq.ai/ots) | Measured utility is a relevant competitive expectation. Its reported gains are vendor claims and provide no estimate for Revo. |
| Toloka | Offers expert-supported model and agent evaluations. [Evaluation](https://toloka.ai/evaluation) | Automated verification is valuable, but cannot be presented as equivalent to independent domain-expert review. |
| Wren AI (prospective user category, not a dataset vendor claim) | Evaluation scenarios use ground-truth SQL and expected outputs for the user's data and use cases. [Documentation](https://docs.getwren.ai/cp/guide/evaluation/overview) | A portable scenario bundle and expected outputs fit a documented workflow. This does not establish procurement interest. |
| Snowflake Cortex Analyst (integration example) | Verified Query Repository associates questions with SQL using the semantic model's logical names. [Documentation](https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repository) | Useful SQL depends on the customer's definitions and dialect; DuckDB correctness does not establish Snowflake compatibility. |
| MotherDuck (prospective user category) | Its product describes natural-language SQL and shared business context; FixIt addresses SQL error repair. [Product](https://motherduck.com/product/), [FixIt](https://motherduck.com/blog/introducing-fixit-ai-sql-error-fixer/) | DuckDB is a practical initial engine. Potential fit is not evidence the company buys external datasets. |

## Research and design consequences

- [Semantic Evaluation for Text-to-SQL with Distilled Test Suites](https://aclanthology.org/2020.emnlp-main.29/)
  supports evaluating queries on multiple constructed databases to approximate
  semantic correctness. Agreement on one fixture is insufficient; finite tests
  still do not prove universal equivalence.
- [Understanding the Effects of Noise in Text-to-SQL](https://aclanthology.org/2024.acl-short.34/)
  examines question and SQL noise in BIRD. Revo should test specification/answer
  agreement before rewarding model disagreement with a purported gold answer.
- [Spider 2.0](https://spider2-sql.github.io/) covers enterprise SQL workflows with
  large schemas and demanding environments. Small synthetic examples should not
  be advertised as demonstrating equivalent enterprise coverage. Its project warns
  against using released gold SQL for supervised fine-tuning because of evaluation
  fairness; Revo should create original cases and keep evaluation lineage private.
- [BIRD-CRITIC / SWE-SQL](https://bird-critic.github.io/) provides SQL debugging
  tasks and replay environments. Repair is an established research category, so
  Revo needs a focused contribution rather than claiming the category is new.

## Recommended MVP

Recommendation/inference: an executable DuckDB business-correctness evaluation
pack for SQL-agent developers, emphasizing queries that execute but calculate the
wrong result. Initial business focus: subscription billing and operational
reporting, using only task meanings explicitly supported by schemas/contracts.

The deliverable includes business questions, documented schemas and units,
correct SQL and expected results, plausible wrong SQL with a discriminating
fixture, versioned evidence, a sandboxed replay command, and failure reports.
Potential differentiators are traceable counterexamples, business meaning,
duplicate/bag handling, join fanout, NULL/missing relationships, and temporal
boundaries. They are hypotheses until potential users evaluate them.

Niche priorities:
1. Wrong-result detection for billing/operations: best match to existing oracle,
   mutation, fixture, and provenance work.
2. SQL repair pairs with replayable counterexamples: useful follow-on, retaining
   whether each failure was model-generated or deliberately authored.
3. Customer semantic-model regression suites: promising later integration,
   dependent on customer definitions and target-engine validation.
4. Broad large-scale training corpus: defer until there is diversity, generation
   yield, licensing evidence, and a downstream utility experiment.

## Bounded pilot specification (new proposal)

Engineering breadth target: at least one fully qualified latest contract in every
existing SQL family. This is not full-catalog qualification. All quarantined rows
remain in the frozen rubric's population.

Pilot target: exactly 12 disclosed showcase records representing 12 materially
different business questions, at least six SQL families, four meaningful schema
designs and two relevant domains. At most one record per task/intent lineage.
Schema renaming, literal/seed changes and paraphrases do not supply this diversity.
Expand qualified contracts if the existing library cannot support the target.

Each selected row needs current qualification and candidate-level execution,
complete applicable verification, full evidence linkage, no unresolved semantics,
and fresh isolated replay. Retain at least one meaningful wrong-answer
counterexample and a second correct formulation per showcase row, while preserving
all stricter contract qualification requirements. Do not equate authored challenge
cases with observed model failures.

Freeze selection rules before inspecting model outcomes. Retain the entire
candidate pool, exclusions, and run costs. Report selected quality and production
yield separately. Reserve task/schema lineage for private evaluation in accordance
with existing isolation rules. The disclosed showcase is thereafter exposed;
it cannot also be claimed as an unseen benchmark.

An optional local-model batch can demonstrate actual production generation:
preflight one already installed eligible model, pin identity and configuration,
then use at most 120 attempted generations and two hours of generation wall time,
one model worker at a time. These caps are proposed operating limits, not quality
thresholds. No downloads, paid providers, or claimed commercial license approvals.
If local model execution cannot be used under repository policy, retain the blocker
and complete a reference-authored internal pack with its origin clearly labeled.
The model-generation milestone remains incomplete in that situation.

Use a separate pilot acceptance path; never weaken the strict 80-record release
validator or pass a 12-row pilot off as the required 80-record dataset. A new
acceptance profile must be explicit, tested, and bound into its manifest.

## Outreach gates and limitations

Discovery discussions can occur now. Sharing the technical sample requires the
pilot's content, evidence, reproducibility, distribution-eligibility, and disclosed
review-status gates to pass. Human review remains pending and no reviewer decisions
may be invented. Rights decisions that need the owner remain external blockers;
an internally verified package may still be blocked from external distribution.

Do not promise that companies cannot reject the product. Useful evidence cannot
guarantee budget, relevance, procurement approval, or superiority to public data.
Small pilot results do not establish a training uplift or population accuracy.
The full 80-record product, remaining catalog qualification, final frozen metrics,
and score above 90 are separate later milestones.

## Execution discipline

Use a durable task/evidence ledger and repeat: inspect, reproduce, implement,
focused verification, stable-source qualification, broader integration, record,
continue. Investigate failures and retain them. Batch immutable recollection after
source stabilization, rather than endlessly invalidating evidence after every edit.
Complete the full regression at coherent certification boundaries. Run relevant
focused tests during development; do not run all ~1,500 tests after every small edit.

Ordinary technical blockers should be repaired autonomously. Ambiguous business
intent, missing permitted model access, rights decisions, spending, and external
communication cannot be resolved by invented assumptions. Record them, continue
independent work, and report any final blocker precisely. Store essential command
evidence durably, with verified copies of temporary artifacts where needed.
