# First Experiment — Verified SQL Data Factory

Status: **Phase 0 — experimental design only. Do not run yet.**

## Design

```text
100 task instances
        ↓
3 candidate solutions per task
        ↓
300 candidates
        ↓
execution verification
        ↓
measure failures
```

Do not target 100,000 records. The point is to validate the loop, not scale it.

## Questions to answer

1. Can we reliably generate useful tasks?
2. Can we deterministically recreate them (same seed → same fixture + verdict)?
3. Can we generate diverse candidate solutions?
4. Can correctness be independently verified (oracle + hidden tests)?
5. How many candidates survive verification?
6. What types of failures occur (taxonomy → FailureEvent)?
7. What is the cost per verified example?
8. Can humans understand and validate the resulting tasks?

## Prerequisites (mapped to phases)

- Phase 1: 100 reproducible tasks across the 10 initial families.
- Phase 2: generation harness with 3-candidate sampling + parsing stats.
- Phase 3: sandbox with timeout + resource capture.
- Phase 4: oracle + hidden suite + failure taxonomy.

## Success criteria (suggested, to be frozen before running)

- 100/100 tasks reproducible from seed.
- Verification verdicts reproducible across re-runs.
- Failure taxonomy covers observed failures with <10% "other".
- Cost-per-verified-example measured end-to-end (GPU + CPU + storage).
- Human audit of a sample: instructions judged clear and tasks valid.
