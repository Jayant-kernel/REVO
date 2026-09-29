# Model value: metrics and statistics

Dataset quality (verified, diverse, reproducible) and model
improvement (better benchmark scores) are measured separately. A great
dataset can fail to move a model; a model can move on one benchmark
without the dataset being broadly valuable.

## Primary metrics (per benchmark, explicit denominators)

- `execution_accuracy` — correct / evaluated.
- `benchmark_pass_rate` — same aggregation, reported separately so
  pass-criteria changes stay visible.
- Family-level accuracy for each of the 10 families
  (`simple_joins`, `multi_joins`, `aggregation`, `cte`, `subqueries`,
  `window_functions`, `temporal`, `deduplication`, `retention`,
  `funnel`).
- Edge-case accuracy where benchmark metadata allows (`null_values`,
  `duplicates`, `ties`, `empty_result`, …).

## Secondary metrics

`parse_rate`, `execution_success_rate`, `invalid_sql_rate`,
`timeout_rate`, `avg/p50/p95_latency_ms`. Latency is reported, never
used as a quality proxy.

## Improvement math

- Absolute improvement = treatment − baseline, in **percentage points**.
- Relative improvement names the baseline denominator; undefined
  (reported as unknown, never zero) when the baseline is zero.
- Error reduction = relative error reduction for accuracy-style
  metrics. Never reported as a bare "8.3% improvement".

## Statistics

Binary correctness on shared instances → exact McNemar test on
discordant pairs + Wilson intervals per arm + Wald interval for the
paired delta. No t-tests on binary data. `n < 30` or fewer than 10
discordant pairs produces explicit limited-power warnings; zero shared
instances yields `INSUFFICIENT_DATA`. Significance is never
manufactured. Repeated runs report mean/std/min/max — one run is
reported as one run, not as general improvement.

## Presentation

`ExperimentComparison` is tables (metrics, families, edge cases) plus a
verdict — never a single model-improvement score.
