# Economics

## Production costs

Tracked per pipeline layer, mirroring `docs/metrics.md`:

`generation_cost`, `execution_cost`, `verification_cost`,
`quality_cost`, `provenance_cost`, `packaging_cost`, plus
`cost_per_candidate`, `cost_per_verified_record`,
`cost_per_golden_record`, `cost_per_million_records`.

Variable and fixed costs stay separated; engineering salary is never
automatically smeared into per-record cost. Every assumption is
recorded on the model.

## Unknowns

Where a cost is unavailable the input stays `None` and surfaces in
`unknown_inputs`. Unknowns never silently become zero: an all-unknown
model yields unknown totals, honestly reported.

## Unit economics

`total_cost`, `golden_records`, `cost_per_golden`,
`cost_per_1000_golden`, `cost_per_million_golden`, each with a
`MEASURED`/`ASSUMED` basis. Scale scenarios (1k/10k/100k/1M) are
labeled `SCENARIO` — planning aids, never forecasts, never price
claims.

## Pricing

`PricingScenario` records price hypotheses per unit (`dataset`,
`record`, `1k records`, `subscription`, `evaluation run`) with cost
basis, target margin, and assumptions — `ASSUMED` until customer
behavior validates them (`MEASURED` requires linked customer
evidence). No willingness-to-pay is inferred from traffic, stars,
downloads, dataset size, or benchmark scores.

## Current status: UNKNOWN

FACT: the cost model, unit economics, scenarios, and pricing
machinery are implemented and tested.

UNKNOWN: every production cost figure and every price — no costs have
been measured and no price has been tested with a customer.
