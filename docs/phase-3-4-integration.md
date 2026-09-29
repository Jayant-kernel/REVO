# Phase 3 + Phase 4 Integration

Status: **validated with real Docker**. This document records the
integrated runtime path, how to run it, and the measured outcomes.
Nothing here is simulated: every verdict below comes from a disposable
container running DuckDB plus the independent Python oracles.

## Runtime path

```text
TaskInstance (frozen Phase 1)
    ↓ hand-authored CandidateSolution (no LLM in this gate)
Phase 3 SandboxExecutor + DockerRunner
    ↓ docker run -i (stdin payload, stdout result)
    ↓ --network none, --read-only, dropped caps, uid 10000, limits
real DuckDB 1.5.5 in image verified-data-factory-sandbox:1.0
    ↓ ExecutionResult (rows/columns/runtime/taxonomy, no verdicts)
Phase 4 verify_candidate (DerivedTaskBackend = same Docker path)
    ↓ oracle (pure Python) -> comparator -> hidden (derived seeds)
    ↓ properties -> metamorphic -> mutations -> performance evidence
VerificationResult (PASS / FAIL / INCONCLUSIVE + evidence)
```

## Commands

```bash
python -m pytest tests/e2e -v          # 10x3 verdict matrix + boundaries + overfit (real Docker)
python -m pytest tests/integration -v  # sandbox boundary + verification e2e suites
python -m pytest tests/ -q             # everything (unit + integration + e2e)
```

Markers: `integration`, `docker`, `e2e` (all require a daemon; unit tests
never do). E2E runs sequentially by design — parallel workers would trip
the session leak-guard with false positives.

## Image (actually inspected)

```text
image:  verified-data-factory-sandbox:1.0
digest: sha256:6ee6badb20867c6426abb0b2ced747a126178f0a99b5bf4d94e65a62c236f7ac
python: 3.12.10
duckdb: 1.5.5
uid: 10000, workdir /work, sandbox config version 1.0
```

Rebuild after any harness change (the image embeds `harness/run.py`):
`docker build -f src/verified_data_factory/sandbox/docker/Dockerfile
-t verified-data-factory-sandbox:1.0 src/verified_data_factory/sandbox`.

## Measured matrix (10 families x correct/obvious/subtle, fixed seeds)

| family | correct | obvious | subtle |
|---|---|---|---|
| sql.joins.simple | PASS | FAIL | FAIL (AVG for SUM) |
| sql.joins.multi | PASS | FAIL | FAIL (qty×amount for qty×price) |
| sql.aggregation.grouped | PASS | FAIL | FAIL (COUNT(amount) vs COUNT(*)) |
| sql.cte.monthly | PASS | FAIL | FAIL (yearly vs monthly buckets) |
| sql.subqueries.exists | PASS | FAIL | FAIL (threshold 0 vs 500) |
| sql.windows.ranked | PASS | FAIL | FAIL (PARTITION BY country) |
| sql.temporal.monthly | PASS | FAIL | FAIL (weekly vs monthly buckets) |
| sql.dedup.latest | PASS | FAIL | FAIL (wrong partition grain) |
| sql.retention.30_day | PASS | FAIL | FAIL (>=2 purchases vs >=1) |
| sql.funnel.completion | PASS | FAIL | FAIL (last-occurrence chaining) |

30/30 match expectations. Every PASS ran hidden (3/3), properties,
metamorphic relations, and mutants through real containers
(asserted applicable/failed counts, not just verdicts).

## Boundary suites (crafted fixtures, real containers)

Retention day 0/29/30/31 + eventless; dedup latest + timestamp tie-break;
funnel order/repeat/missing/cross-session; temporal window edges + month
transitions; window ties/gaps/running totals/partitions — all agree
(candidate SQL vs oracle vs spec).

## Defects found and fixed by this gate (with regression tests)

1. `docker cp` rejected on read-only-rootfs containers -> stdin/stdout
   delivery (runner/harness/executor rework, `docker cp` eliminated).
2. Stale harness inside the prebuilt image -> rebuild discipline documented.
3. Oracle `SUM` over all-NULL emitted 0, SQL says NULL -> oracle fixed +
   unit regression test.
4. Equivalent mutants counted against suites (`INNER->LEFT` with WHERE on
   the right side; date-only `WHERE` drop on all-2025 fixtures) ->
   replaced `join-inner-to-left` with discriminating `join-inner-to-cross`;
   dropped vacuous operator from aggregation (both documented).
5. `order_date` in windows order spec is not an output column ->
   narrowed to checkable keys + logged interpretation.
6. OOM-by-streaming-aggregate doesn't allocate (optimizer) ->
   memory validation via cgroup caps instead of hopeful OOM races.
7. Phase 2 parser intercepts non-SELECT before the sandbox policy gate ->
   adversarial policy tests construct candidates directly (documented).

## Known limits of this gate

- Windows 11 + Docker Desktop (Linux containers); re-run on Linux CI.
- DuckDB optimizer awareness required when authoring adversarial workloads.
- E2E is sequential (~2 min for 30 cells on warm engine; first cold run slower).
