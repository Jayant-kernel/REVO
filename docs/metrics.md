# Metrics — Verified SQL Data Factory

Status: **Phase 0 — definitions only. Nothing is collected yet.**

## Generation metrics

```text
generation_success_rate   # candidates produced / attempts
parse_success_rate        # candidates parsing as valid SQL / produced
```

## Verification metrics

```text
execution_pass_rate       # candidates executing without error / executed
hidden_test_pass_rate     # candidates passing hidden suite / executed
property_test_pass_rate   # candidates passing property suite / executed
metamorphic_pass_rate     # candidates passing metamorphic checks / executed
mutation_score            # mutants killed / total mutants (suite strength)
performance_pass_rate     # candidates within perf budget / executed
```

## Dataset metrics

```text
duplicate_rate
semantic_duplicate_rate
task_coverage             # families × difficulty cells filled / planned
difficulty_distribution   # histogram over difficulty bands
edge_case_coverage        # edge-case tags exercised / required
human_audit_failure_rate  # audited records rejected / audited
```

## Economics

```text
cost_per_candidate
cost_per_verified_example
GPU_cost
CPU_verification_cost
storage_cost
```

## Key commercial metric

> **Cost per genuinely useful verified example.**

"Genuinely useful" = passes hidden + property/metamorphic gates against a
strong (high-mutation-score) suite, passes quality/dedup review, and survives
human audit sampling. Volume without this qualifier is not reported as value.
