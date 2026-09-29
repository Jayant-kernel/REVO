# Pilot template

## Proposal

- Product release: `<release_id>`
- Customer segment: `<segment>`
- Use case: `<use case>`

## Success criteria (configurable, agreed before start)

| ID | Metric | Threshold | Direction |
|---|---|---|---|
| ex-1 | execution_accuracy delta | +X pp | gte |
| ex-2 | invalid_sql_rate | ≤ Y | lte |

No universal thresholds — values are agreed per pilot and recorded in
`business.pilot.SuccessCriterion`.

## Lifecycle

`PLANNED` → `ACTIVE` → `COMPLETED` (`PAUSED`/`CANCELLED` exits).
Terminal states are final.

## Package

`factory business export` produces `pilot/` with `product/`,
`benchmark/` (public view only — answers need explicit opt-in),
`evaluation/`, `results/`, `provenance/`.

## Close-out

Evaluate criteria (`MET`/`UNMET`/`UNEVALUATED`), link feedback ids,
record willingness signals with evidence references. Negative results
stay visible.
