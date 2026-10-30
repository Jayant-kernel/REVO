# Phase 3 CTE `INFRA_INCONCLUSIVE` Diagnosis

Historical smoke evidence recorded `sql.cte.monthly` operator
`agg-sum-to-avg` as `INFRA_INCONCLUSIVE` with reason `infra-SANDBOX_ERROR`.
That classification is transport/runtime evidence, not a semantic kill and was
therefore excluded from the historical mutation score.

One retry was in scope because it used the same hand-authored candidate SQL,
the same deterministic task seed (`1`), the ordinary `SandboxBackend`, and no
model or frozen-run operation. The retry is captured in
`phase3-sql-mutation-classifications.json` under `sql.cte.monthly`.

The retry completed without infrastructure faults: `agg-sum-to-avg`,
`order-flip`, and `where-clause-drop` are all `SEMANTIC_KILL` with
`result-mismatch`; the CTE row has `inconclusive: 0`, `survived: 0`, and
`mutation_score: 1.0`.

This resolves only the historical mutation-harness incident for that
controlled CTE rerun. It does not relabel any frozen run or claim that a
general Docker reliability issue is eliminated.

The named real-Docker regression
`tests/integration/verification/test_verify_e2e.py::test_cte_year_filter_drop_is_discriminated_end_to_end`
also passed on this checkout (3.65s). It exercises seed `401` through the
Phase 3 sandbox and confirms both `where-clause-drop` and `agg-sum-to-avg`
are `result-mismatch` semantic kills. The prior `INFRA_INCONCLUSIVE` remains
historical transport evidence; the new run does not rewrite it.
