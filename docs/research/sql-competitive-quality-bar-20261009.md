# Competitive quality bar for Revo's automated pre-review candidate

Research checked 9 October 2026. This is a recommendation, not a certification,
market-wide ranking, or replacement for the frozen engineering rubric.

## Local evidence and limits

The latest saved catalog inspected is
`scratch/funnel_experiment/engineering/catalog-two-families-v17.json`:
5 FULLY_VERIFIED, 52 QUARANTINED, 57 total, four qualified SQL families.
`checkpoint-two-families-v17-summary.json` retains detailed category counts.
The checkpoint reports 1,487 full-regression passes and strict typing across
177 source files. These tests were not rerun for this research note.
The forward 80-record product has zero accepted records; engineering score
remains NOT_COMPUTABLE. Historical 232-row production data is a different population.

Some overview documentation is older than the checkpoint: architecture.md still
describes a planning-only phase, and the handoff contains earlier catalog totals.
The next implementer must reconcile documentation against source-bound authority
and executions rather than treat a prose status as proof.

There is no measured basis for saying 80% of the whole factory is complete.
Contract coverage, effort completion, automated engineering score, dataset
correctness, and commercial readiness are different quantities. The historical
52/100 was a different commercial assessment, not current SQL accuracy.

## Public comparison

This is a targeted comparison of relevant public alternatives, not an exhaustive
inventory of every competitor. Public offerings do not reveal vendors' original
MVPs, private quality processes, procurement requirements, or willingness to buy.

| Alternative | Primary-source evidence | Consequence for Revo |
|---|---|---|
| OmniSQL / SynSQL-2.5M | Its repository reports over 2.5 million examples across more than 16,000 databases, with synthesis and evaluation code. Its stated dialect is SQLite. [Repository](https://github.com/RUCKBReasoning/OmniSQL) | Competing on raw size is an unsuitable near-term objective. Show a specific, measured verification advantage instead. |
| Gretel synthetic text-to-SQL | The dataset card reports 105,851 examples across 100 domains. [Dataset card](https://huggingface.co/datasets/gretelai/synthetic_text_to_sql) | A small generic question/SQL file alone offers weak differentiation. |
| Spider 2.0 | Enterprise-oriented workflows include large schemas and multiple database environments. [Project](https://spider2-sql.github.io/) | Ten syntax families do not establish enterprise realism. Revo should declare its smaller, engine-specific scope. |
| BIRD-CRITIC / SWE-SQL | Provides SQL diagnostic tasks and execution-based evaluation across dialects. [Project](https://bird-critic.github.io/) | SQL repair and execution-backed evaluation already exist. The proposed niche is not a new category. |
| Scale Data Engine | Offers generation, expert labels, evaluation, and curation around model failures. [Product](https://scale.com/data-engine) | A useful product includes diagnosis and an improvement workflow, not merely rows. Revo has no equivalent expert-review evidence yet. |
| Surge AI | Offers training data, evaluations and RL environments, and advertises measured model gains. [Offering](https://surgehq.ai/ots) | Utility is an important competitive question. These are vendor claims, not independently verified estimates of Revo's potential gains. |
| Wren AI | Its documented evaluation workflow uses questions, ground-truth SQL and expected outputs. [Documentation](https://docs.getwren.ai/cp/guide/evaluation/overview) | A replayable scenario package fits a documented user workflow; this does not establish purchase interest. |
| Snowflake Cortex Analyst | Verified Query Repository ties questions to SQL over logical semantic-model names. [Documentation](https://docs.snowflake.com/en/user-guide/views-semantic/verified-query-repository) | Customer definitions and target-engine compatibility matter. DuckDB results do not certify Snowflake behavior. |

## Research implications

Multi-database test-suite evaluation can better approximate semantic correctness
than matching on one database. It remains finite testing, not a universal proof.
[Distilled test suites](https://aclanthology.org/2020.emnlp-main.29/)

Research on BIRD noise examines problems in questions and reference SQL. Therefore
the reference answer must itself be challenged; model disagreement is not enough
to establish a model error.
[Noise study](https://aclanthology.org/2024.acl-short.34/)

SQLSolver offers SQL equivalence verification but documents unsupported cases,
timeouts, and incomplete recognition of equivalent queries. Its README cautions
that even NEQ or UNKNOWN may occur for equivalent pairs. A future adapter needs
carefully mapped outcomes; it cannot treat every non-EQ result as a witnessed
semantic error. [SQLSolver](https://github.com/SJTU-IPADS/SQLSolver)

VeriEQL investigates bounded equivalence with integrity constraints and generated
counterexamples. Bounds and schema assumptions must accompany any claim.
[VeriEQL](https://arxiv.org/abs/2403.03193)

Recommendation: retain the current oracle, alternate SQL, challenge, relation,
and fuzz layers. Strengthen their independence and observation quality. Consider
a bounded formal-verification experiment later; do not make a new solver stack a
prerequisite for delivering this candidate. Query equivalence does not establish
that either query expresses an ambiguous natural-language business request.

## Proposed product focus

The strongest near-term hypothesis is a DuckDB business-correctness evaluation
and repair pack: queries that execute successfully but calculate the wrong answer,
with small reproducible counterexamples and traceable acceptance evidence.
Billing, fulfillment, manufacturing and retention are useful starting scenarios.
The broader 80-row candidate must still meet the frozen five-domain requirement.

Prioritize:

1. Duplicate-row multiplicity and join fanout errors.
2. NULL, orphan and unmatched-relationship mistakes.
3. Incorrect event selection, tie handling and time-window boundaries.
4. Incorrect aggregation populations and business exclusions.
5. Reproducible correct/wrong pairs and readable explanations of the difference.

These priorities are an inference from Revo's current capabilities and public
alternatives. Their customer value remains unvalidated. Do not claim that all
competitors lack these features or that a company cannot reject the dataset.

## Measurable automated exit, not a percentage

Finish a frozen, automatically accepted 80-record candidate under the existing
specification: eight per family, at least 40 materially different instructions,
ten schema roles, five domains, and all existing construct/edge/novelty gates.
Retain human-review status PENDING and commercial release restrictions.

Before calling it ready for human review:

- Every selected record has current qualification and actual candidate-level
  verification; authored references are not misrepresented as model generation.
- Selected content has no unresolved semantic failures or duplicate displacement.
- The checker rejects the required executable wrong-query challenges and accepts
  substantive correct alternatives. Counts and populations are explicit.
- Realistic distributions and relevant boundary behaviors are actually observed.
- Fresh exported artifacts replay through the real sandbox in a relocated clean
  environment; interruption, tamper and stale-evidence rejection are exercised.
- Development, showcase and evaluation roles remain isolated. Public benchmarks
  are reference material, not silently repackaged private examples.
- A fresh regression, typing, lint and frozen-asset guard pass on the final source
  identity. Any later relevant change invalidates affected evidence.

Compare the full verifier with execution-only and ordinary-fixture comparison on
the same frozen correct/wrong population. Report false acceptance, false rejection,
abstention, runtime and results by family. This measures checker discrimination,
not training benefit or broad market superiority. A curated adversarial challenge
set is not a representative estimate of real-world error prevalence.

Where possible, test on additional cases not used to tune the verifier. If one
agent authors both the checker and evaluation, disclose that limitation. Thousands
of correlated seed executions do not establish thousands of independent tasks.
If evaluation cases inform repairs, retain the first result, move those cases to
development, and use newly reserved material for the next generalization check.

The unchanged engineering rubric is a separate assessment over its defined
populations, including quarantined contracts. An 80-row passing subset cannot earn
full-catalog credit automatically. Produce criterion-specific inputs before the
authorized scoring phase. A result above 90 is an aspiration, not a promised
outcome or evidence of 90% SQL accuracy.

## Human review and outreach

Human quality review is deferred until these automated candidate gates pass,
as requested. Do not delete review machinery, invent votes, or label the candidate
human-approved. Missing business intent is a specification dependency, not a
license to guess: quarantine the affected contract and continue specified work.

Prepare a representative 10-20-example preview only after eligibility filtering,
with the selection method disclosed. It is a preview, not an unbiased quality
estimate. External sharing still needs the appropriate rights decision and user
authorization. No company contact, publication or human review is part of this
engineering prompt. No fixed completion percentage determines share readiness.

## Deliverable

Use `docs/production/automated-quality-continuation-prompt-20261009.md` for the
next AI. It extends the earlier bounded pilot proposal to the full automated
80-record candidate, without weakening the original rubric or release gates.
The research skill informed the cited comparison and evidence-based exit criteria.
Agent Reach's Jina route was unavailable for the arXiv check; the public paper was
read through the available web tool instead. No factory code or run was modified.
