# Phase 3 Diagnostic

## Scope

Read-only analysis of `runs/premium-qualification-080`. No generation, execution of candidate SQL, or modification of run artifacts occurred.

## Reconciliation

- Candidates: 240 (source: candidates/candidates.jsonl $[*].results[*])
- Verification passes: 128 (source: verification/verification.jsonl $[?(@.verdict == 'PASS')])
- Semantic-duplicate exclusions: 85 (source: quality/export/excluded.jsonl $[?('SEMANTIC_DUPLICATE' in @.reasons)])
- Selected Goldens: 37 (source: quality/export/golden.jsonl $[*])

## Duplicate Decomposition

- Task level: 46/80 = 57.5%
- Candidate level: 193/240 = 80.4%
- Counterfactual excluding siblings: 57.5%
- Counterfactual excluding siblings and same-template collisions: 0.0%
- Tautological retrospective: this reports the same observed semantic groups after excluding named categories from that same observation. It is not a causal estimate or prediction for a new run.

## Contract Readiness

Statuses are `yes`, `no`, or `unknown`; every cell's source is in the JSON report.

| Family | Fully verified | Templates |
| --- | --- | --- |
| aggregation | 8/8 | 8/8 fully verified across 8 checks |
| cte | 8/8 | 8/8 fully verified across 8 checks |
| deduplication | 4/4 | 4/4 fully verified across 8 checks |
| funnel | 7/8 | 7/8 fully verified across 8 checks |
| multi_joins | 4/4 | 4/4 fully verified across 8 checks |
| retention | 4/4 | 4/4 fully verified across 8 checks |
| simple_joins | 4/4 | 4/4 fully verified across 8 checks |
| subqueries | 5/5 | 5/5 fully verified across 8 checks |
| temporal | 8/8 | 8/8 fully verified across 8 checks |
| window_functions | 4/4 | 4/4 fully verified across 8 checks |

| Template | Template validates | Fixture generator | Independent oracle | Registry entry | Adversarial case | Reference SQL mapping | Mutation applicability | Focused test | Fully verified |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sql.aggregation.fulfillment_sla_dashboard | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.aggregation.grouped | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.aggregation.manufacturing_line_scrap | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.aggregation.payment_net_settled | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.aggregation.product_unique_conversion | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.aggregation.support_sla_breaches | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.aggregation.top_category_sales | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.aggregation.warehouse_throughput | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.cte.category_descendant_sales | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.cte.customer_first_month_repeat | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.cte.inventory_net_flow | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.cte.logistics_depot_delay | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.cte.monthly | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.cte.order_line_reconciliation | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.cte.saas_mrr_changes | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.cte.session_funnel_completion | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.dedup.education_grade_revisions | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.dedup.latest | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.dedup.payments_latest_profile | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.dedup.refund_prefer_approved | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.funnel.checkout_paid_session | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.funnel.completion | yes | yes | yes | yes | yes | yes | no | yes | no |
| sql.funnel.curriculum_gate_completion | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.funnel.kyc_document_approval | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.funnel.logistics_parcel_delivery | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.funnel.parcel_exception_recovery | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.funnel.saas_activation_payment | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.funnel.support_resolution_chain | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.joins.clinic_scheduled_clinician | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.joins.education_completed_enrollment | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.joins.logistics_final_leg | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.joins.manufacturing_approved_supplier | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.joins.multi | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.joins.payments_country_transfer | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.joins.saas_paid_invoices | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.joins.simple | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.retention.30_day | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.retention.clinic_followup_window | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.retention.media_week_two_return | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.retention.saas_repeat_payment | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.subqueries.customer_outreach | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.subqueries.education_all_required | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.subqueries.exists | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.subqueries.payments_no_settlement | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.subqueries.support_unresolved_reopen | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.temporal.clinic_weekly_visits | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.temporal.inventory_daily_stock | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.temporal.logistics_service_level_as_of | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.temporal.manufacturing_shift_downtime | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.temporal.media_first_full_week_viewers | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.temporal.monthly | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.temporal.saas_account_snapshot | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.temporal.saas_trial_activation | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.windows.logistics_previous_stop | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.windows.media_previous_play | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.windows.payments_risk_rank | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sql.windows.ranked | yes | yes | yes | yes | yes | yes | yes | yes | yes |

### UNKNOWN_REFERENCE_SQL


## Task Survival

A task survives before dedup if at least one candidate has verification verdict `PASS`; after dedup it survives when selected Golden.

| Family | Tasks | Before dedup PASS | After dedup selected Golden |
| --- | --- | --- | --- |
| aggregation | 8 | 6 | 5 |
| cte | 8 | 8 | 5 |
| deduplication | 8 | 3 | 3 |
| funnel | 8 | 0 | 0 |
| multi_joins | 8 | 8 | 5 |
| retention | 8 | 6 | 5 |
| simple_joins | 8 | 8 | 5 |
| subqueries | 8 | 4 | 3 |
| temporal | 8 | 3 | 3 |
| window_functions | 8 | 4 | 3 |

| Template | Tasks | Before dedup PASS | After dedup selected Golden |
| --- | --- | --- | --- |
| sql.aggregation.grouped | 2 | 2 | 1 |
| sql.aggregation.manufacturing_line_scrap | 2 | 0 | 0 |
| sql.aggregation.payment_net_settled | 1 | 1 | 1 |
| sql.aggregation.support_sla_breaches | 1 | 1 | 1 |
| sql.aggregation.top_category_sales | 1 | 1 | 1 |
| sql.aggregation.warehouse_throughput | 1 | 1 | 1 |
| sql.cte.inventory_net_flow | 2 | 2 | 1 |
| sql.cte.logistics_depot_delay | 2 | 2 | 1 |
| sql.cte.monthly | 2 | 2 | 2 |
| sql.cte.saas_mrr_changes | 2 | 2 | 1 |
| sql.dedup.education_grade_revisions | 2 | 2 | 2 |
| sql.dedup.latest | 2 | 1 | 1 |
| sql.dedup.payments_latest_profile | 2 | 0 | 0 |
| sql.dedup.refund_prefer_approved | 2 | 0 | 0 |
| sql.funnel.completion | 2 | 0 | 0 |
| sql.funnel.logistics_parcel_delivery | 2 | 0 | 0 |
| sql.funnel.saas_activation_payment | 2 | 0 | 0 |
| sql.funnel.support_resolution_chain | 2 | 0 | 0 |
| sql.joins.clinic_scheduled_clinician | 2 | 2 | 1 |
| sql.joins.education_completed_enrollment | 2 | 2 | 1 |
| sql.joins.logistics_final_leg | 2 | 2 | 1 |
| sql.joins.manufacturing_approved_supplier | 2 | 2 | 1 |
| sql.joins.multi | 2 | 2 | 2 |
| sql.joins.payments_country_transfer | 2 | 2 | 1 |
| sql.joins.saas_paid_invoices | 2 | 2 | 2 |
| sql.joins.simple | 2 | 2 | 1 |
| sql.retention.30_day | 2 | 2 | 2 |
| sql.retention.clinic_followup_window | 2 | 2 | 1 |
| sql.retention.media_week_two_return | 2 | 0 | 0 |
| sql.retention.saas_repeat_payment | 2 | 2 | 2 |
| sql.subqueries.customer_outreach | 2 | 2 | 1 |
| sql.subqueries.education_all_required | 2 | 1 | 1 |
| sql.subqueries.exists | 2 | 1 | 1 |
| sql.subqueries.payments_no_settlement | 1 | 0 | 0 |
| sql.subqueries.support_unresolved_reopen | 1 | 0 | 0 |
| sql.temporal.clinic_weekly_visits | 2 | 0 | 0 |
| sql.temporal.inventory_daily_stock | 2 | 1 | 1 |
| sql.temporal.monthly | 2 | 2 | 2 |
| sql.temporal.saas_trial_activation | 2 | 0 | 0 |
| sql.windows.logistics_previous_stop | 2 | 0 | 0 |
| sql.windows.media_previous_play | 2 | 2 | 1 |
| sql.windows.payments_risk_rank | 2 | 0 | 0 |
| sql.windows.ranked | 2 | 2 | 2 |

## Funnel Triage

- Classification rule: A funnel row is labelled 'model error' only when its stage is execution (candidate exists in execution/triples.jsonl and execution.status != 'SUCCEEDED') or initial_oracle_match (execution.status == 'SUCCEEDED' and verification.comparison.match is false). All other stages are 'undetermined'.
- Derivation proof: failure_stage is derived in _funnel_triage from execution/triples.jsonl before verification/verification.jsonl comparison fields; labels are then a pure function of that derived stage.

- `sql.funnel.completion.v3.92b35c0b8f07.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.00.b651a6ed6729`: initial_oracle_match; model error
- `sql.funnel.completion.v3.92b35c0b8f07.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.01.fc787d8dbe30`: initial_oracle_match; model error
- `sql.funnel.completion.v3.92b35c0b8f07.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.02.1bb80ca4b66c`: initial_oracle_match; model error
- `sql.funnel.completion.v3.cd2d9148df93.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.00.c0a8d6cf6db3`: initial_oracle_match; model error
- `sql.funnel.completion.v3.cd2d9148df93.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.01.1c31ef9f6f69`: initial_oracle_match; model error
- `sql.funnel.completion.v3.cd2d9148df93.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.02.ef691b91a347`: initial_oracle_match; model error
- `sql.funnel.logistics_parcel_delivery.v1.1052ca7347d2.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.00.43bd0bd77d34`: initial_oracle_match; model error
- `sql.funnel.logistics_parcel_delivery.v1.1052ca7347d2.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.01.24ebc96500bf`: execution; model error
- `sql.funnel.logistics_parcel_delivery.v1.1052ca7347d2.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.02.8af23c9d5320`: execution; model error
- `sql.funnel.logistics_parcel_delivery.v1.beb79ae10082.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.00.1387066629fd`: initial_oracle_match; model error
- `sql.funnel.logistics_parcel_delivery.v1.beb79ae10082.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.01.b85d83320b5c`: initial_oracle_match; model error
- `sql.funnel.logistics_parcel_delivery.v1.beb79ae10082.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.02.725cd2633d90`: initial_oracle_match; model error
- `sql.funnel.saas_activation_payment.v1.09549ea68f04.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.00.5d891f915d39`: initial_oracle_match; model error
- `sql.funnel.saas_activation_payment.v1.09549ea68f04.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.01.e761b092a5c8`: initial_oracle_match; model error
- `sql.funnel.saas_activation_payment.v1.09549ea68f04.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.02.e59ca0cdda8a`: execution; model error
- `sql.funnel.saas_activation_payment.v1.b83665ca614a.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.00.c5ef549c5610`: execution; model error
- `sql.funnel.saas_activation_payment.v1.b83665ca614a.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.01.c8d3b90ab916`: execution; model error
- `sql.funnel.saas_activation_payment.v1.b83665ca614a.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.02.2ef75e09b894`: initial_oracle_match; model error
- `sql.funnel.support_resolution_chain.v1.0eb090742fb4.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.00.9865ef5dca38`: HIDDEN_MISMATCH; undetermined
- `sql.funnel.support_resolution_chain.v1.0eb090742fb4.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.01.25d6adfdb5f8`: HIDDEN_MISMATCH; undetermined
- `sql.funnel.support_resolution_chain.v1.0eb090742fb4.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.02.600387db2bc4`: initial_oracle_match; model error
- `sql.funnel.support_resolution_chain.v1.4e6a714fd545.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.00.f8a5d3802d88`: initial_oracle_match; model error
- `sql.funnel.support_resolution_chain.v1.4e6a714fd545.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.01.d39a0771e438`: initial_oracle_match; model error
- `sql.funnel.support_resolution_chain.v1.4e6a714fd545.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.02.87d79f0126e8`: initial_oracle_match; model error

### Representative Model-Error Diffs

- `sql.funnel.logistics_parcel_delivery.v1.1052ca7347d2.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.01.24ebc96500bf`: execution_failed; execution={'code': 'EXECUTION_ERROR', 'detail': {}, 'message': 'candidate SQL failed in sandbox: Binder Error: Ambiguous reference to column name "entity_id" (use: "sg.entity_id" or "fc.entity_id")\n\nLINE 64:     entity_id,\n             ^'}; differences=[]
- `sql.funnel.logistics_parcel_delivery.v1.1052ca7347d2.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.02.8af23c9d5320`: execution_failed; execution={'code': 'EXECUTION_ERROR', 'detail': {}, 'message': 'candidate SQL failed in sandbox: Binder Error: Referenced column "entity_id" not found in FROM clause!\nCandidate bindings: "step_order", "amount", "status", "is_new_session"\n\nLINE 61:     entity_id\n             ^'}; differences=[]
- `sql.funnel.saas_activation_payment.v1.09549ea68f04.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.02.e59ca0cdda8a`: execution_failed; execution={'code': 'EXECUTION_ERROR', 'detail': {}, 'message': 'candidate SQL failed in sandbox: Binder Error: Column "step" does not exist on left side of join!'}; differences=[]
- `sql.funnel.completion.v3.92b35c0b8f07.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.00.b651a6ed6729`: result_mismatch; execution=None; differences=[{'actual': [], 'expected': [2, 3, False], 'index': 1}, {'actual': [], 'expected': [5, 3, False], 'index': 4}, {'actual': [], 'expected': [6, 2, False], 'index': 5}]
- `sql.funnel.completion.v3.92b35c0b8f07.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.01.fc787d8dbe30`: result_mismatch; execution=None; differences=[{'actual': [], 'expected': [2, 3, False], 'index': 1}, {'actual': [], 'expected': [5, 3, False], 'index': 4}, {'actual': [], 'expected': [6, 2, False], 'index': 5}]
- `sql.funnel.completion.v3.92b35c0b8f07.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.02.1bb80ca4b66c`: result_mismatch; execution=None; differences=[{'actual': [], 'expected': [1, 4, True], 'index': 0}, {'actual': [], 'expected': [2, 3, False], 'index': 1}, {'actual': [], 'expected': [4, 2, False], 'index': 3}]

### Hidden Mismatch Inspections

- `sql.funnel.support_resolution_chain.v1.0eb090742fb4.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.00.9865ef5dca38`: unknown; UNKNOWN: the frozen artifact records only hidden-case failure metadata, not the hidden fixture or expected/actual rows needed to distinguish a candidate defect from an oracle, fixture, or prompt defect.
- `sql.funnel.support_resolution_chain.v1.0eb090742fb4.huihui-devstral-small-2-24b-instruct-2512-abliterated-latest.01.25d6adfdb5f8`: unknown; UNKNOWN: the frozen artifact records only hidden-case failure metadata, not the hidden fixture or expected/actual rows needed to distinguish a candidate defect from an oracle, fixture, or prompt defect.

## Open Questions

- Oracle semantic correctness requires independent human/domain review; existing artifacts cannot establish it.
- Prompt ambiguity cannot be distinguished from model error solely from recorded candidate outputs.
- Cross-schema behavioral equivalence is unknown because the catalog has no shared probe-fixture protocol.

Full machine-readable sections, sources, and collision detail are in the adjacent JSON report.
