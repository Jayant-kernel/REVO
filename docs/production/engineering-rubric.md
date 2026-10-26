# Frozen automated engineering rubric — engineering-1.0

This is a new engineering assessment, not a commercial release approval. The
official historical assessment remains **52/100**. Human review, rights and
commercial approvals earn no points. Learning value is **NOT MEASURED**.

The machine-readable authority is `configs/package_a/engineering-rubric.json`.
The frozen measuring script is `scripts/engineering_score.py`. Both, this
document, and the scoring tests are hashed in the Phase 0 lock **before** the
baseline is measured. The target is 86 or above, not a guaranteed result.

| Dimension | Maximum | Numeric acceptance |
|---|---:|---|
| Semantic/result correctness | 20 | 0 typed comparator failures; 0 untyped production callers; 0 uncovered/violated contract rules |
| Evaluation discrimination | 20 | 0 challenge-deficient contracts; all contracts have 4 distinct fixtures and 2 executed relations that each kill a wrong query |
| Instruction/schema completeness | 10 | 0 missing public rules, incomplete schemas or incomplete output contracts |
| Diversity/coverage/realism | 15 | 0 undisposed behavioral duplicate clusters; all 10 families/16 constructs/15 edges; 3 cardinality/boundary profiles per contract |
| Pipeline reliability | 10 | 0 parity failures, crash/retry/cap/accounting failures, or missing protocol receipts |
| Reproducibility/freshness | 10 | 0 missing dependency manifests, replay failures, or stale-evidence false acceptances |
| Isolation/leakage | 10 | 0 rename-isolation failures, unresolved cross-role overlaps, or prompt-boundary failures |
| Export usability | 5 | 0 membership/empty release failures, typed round-trip failures, or checksum-completeness failures |

Each dimension has the fixed binary subcriteria/point weights in JSON. Credit
requires a nonempty executed population, zero execution failures, and fresh,
hash-bound receipts. Missing/inconclusive evidence receives zero, not full
credit. Quarantined contracts remain in coverage denominators; demotion does
not increase coverage points by shrinking the population. An artifact may
establish a narrower, passing phase without earning a full-catalog criterion.

For each metric, the Phase 11 input names a receipt with `evidence_id`, producer,
nonempty `source_hashes`, `population_count > 0`, `checks_run > 0`,
`execution_failures == 0`, and `metrics`. The scorer checks the artifact digest,
all dependency hashes, and the requested numeric metric. It never trusts a
bare PASS label. The producing phase must independently derive that metric
from executed cases; a scored result is only as sound as that producer.

The scorer awards all or zero of each fixed subcriterion's points. It sums
them without rounding. Every absent/stale receipt records a deduction reason.
No score is computed until Phase 11. Negative tests prohibit credit for empty
populations, failed execution, stale sources, edited locks, or missing metrics.

Thresholds: 20 executable witnessed wrong queries, 3 qualified correct SQL
alternatives, 3 valid non-equivalent semantic mutants, 2 discriminating
relations, 4 distinct fixtures per contract; random fuzz >=300 per seed
(1,43,94001), mandatory observed behavior >=20/seed or explicitly targeted,
and 0 unresolved divergences/survivors. The new forward dataset must have
80 records, 8/family, >=40 distinct instructions, >=10 schema roles across
>=5 domains and <=12 rows per schema. Invalid SQL and infrastructure outcomes
do not establish semantics. Every not-applicable finding needs a domain reason.

Measurement commands (Phase 11 only):

```
python scripts/engineering_score.py --input scratch/funnel_experiment/engineering/score-input.json --output scratch/funnel_experiment/engineering/score.json
```

Threshold changes after the lock require a new explicitly identified rubric,
retained old hashes, and separately reported results; they cannot be used to
repair a failing score in this campaign.
