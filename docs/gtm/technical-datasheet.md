# Technical datasheet

Generated per release by `business.positioning.technical_datasheet`
from actual artifacts — never hand-edited claims.

| Field | Source |
|---|---|
| domain | fixed: analytical SQL |
| task families | release metrics `family_distribution` |
| sql dialect | fixed: DuckDB |
| verification method | fixed: independent oracles + hidden/property/metamorphic + mutation |
| quality methodology | fixed: Phase 5 pipeline |
| provenance methodology | fixed: Phase 6 pipeline |
| dataset formats | manifest `output_format` |
| schema version | manifest `schema_version` |
| release version | manifest `release_id` |
| record count | manifest `record_count` |
| coverage | release metrics, or UNKNOWN |
| known limitations | analytical SQL only; no improvement claims without experiments; no pricing claims |
| reproducibility level | caller-supplied, default UNKNOWN |
| benchmark id | linked benchmark, or UNKNOWN |

Unknown values render as UNKNOWN, never as zeros or guesses.
