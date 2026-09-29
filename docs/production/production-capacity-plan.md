# Production capacity plan

All forward-looking figures below are **ESTIMATES**, not production results.

## Observed historical evidence

`production-001` generated 1,500 candidates from 500 tasks between the candidate artifact creation and final modification times (about 15.3 hours): approximately **1.6 candidates/minute**. Its sandbox stage took about 17.7 minutes for 1,500 candidates (about **85 candidates/minute**). Its verification artifact took about 104 minutes for 1,500 candidates (about **14 candidates/minute**). These are workstation observations, not hardware guarantees.

`production-001` stored roughly 61 MB across tasks, candidates, execution triples, verification results, quality records, and Golden exports. This is an observed artifact size for that run, excluding Docker images, model weights, interpreter caches, and future release files.

The targeted qualification generated 246 candidates in about 2.1 hours (about **1.9 candidates/minute**). It was deliberately skewed toward repaired families, so it is not a production-yield forecast.

## Yield context

`production-001` produced 232 Golden records from 1,500 candidates: **15.47% observed Golden yield**. The current targeted qualification produced 80 Goldens from 246 targeted candidates: **32.5% observed targeted yield**. Neither proves the yield for the next balanced production run.

At the historical production-001 yield, reaching 1,000 Goldens would require about 6,466 candidates, or about 2,156 tasks at three candidates per task. This is an **ESTIMATE** only. Batch 1 must measure actual yield before any continuation calculation.

## Initial batch estimate

The frozen Batch 1 plan is 500 tasks and 1,500 candidates. Using observed generation rates, generation may take roughly 13–16 hours, plus sandbox, verification, quality, audit, and storage overhead. Budget caps are safeguards, not hardware reservations: 4,000 tasks, 12,000 candidates, and 1,440 wall-clock minutes.

## Monitoring priorities

Aggregation is historically healthy. CTE, temporal, and window families were recently repaired and require close monitoring. Funnel has historically been weaker; retention should be monitored. No family has a forced Golden quota.
