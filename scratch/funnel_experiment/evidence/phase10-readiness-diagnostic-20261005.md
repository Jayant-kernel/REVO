# Phase 10 Readiness Diagnostic

## Authoritative Result

- Current contracts: 57
- Fully verified: 50
- Funnel contracts: 8; fully verified funnels: 1
- Quarantined: 7; not ready: 0
- The prior `56 fully verified / all 7 funnels passed` claim is superseded.
- This is a readiness record, not a model, release, rights, or historical-run claim.

## Evidence Authority

The contract evidence index is authoritative. The matrix and manifest are derived from it; the count report independently reads the index and matrix without importing this generator.
Index: `sha256:a934caa02250bbc1b91be2a78eb1225e849a400303c8193fe24db7c7676b05b7`.
Superseded manifest SHA-256: `f589e0a7097045592d4433d1bf87915121aa6e6d2efee665850c30256d9e0381`.

## Contract Status

| Contract | Version | Status | Journal evidence |
| --- | ---: | --- | ---: |
| `sql.aggregation.fulfillment_sla_dashboard` | 1 | FULLY_VERIFIED | 0 |
| `sql.aggregation.grouped` | 2 | FULLY_VERIFIED | 0 |
| `sql.aggregation.manufacturing_line_scrap` | 1 | FULLY_VERIFIED | 0 |
| `sql.aggregation.payment_net_settled` | 1 | FULLY_VERIFIED | 0 |
| `sql.aggregation.product_unique_conversion` | 1 | FULLY_VERIFIED | 0 |
| `sql.aggregation.support_sla_breaches` | 1 | FULLY_VERIFIED | 0 |
| `sql.aggregation.top_category_sales` | 1 | FULLY_VERIFIED | 0 |
| `sql.aggregation.warehouse_throughput` | 1 | FULLY_VERIFIED | 0 |
| `sql.cte.category_descendant_sales` | 1 | FULLY_VERIFIED | 0 |
| `sql.cte.customer_first_month_repeat` | 1 | FULLY_VERIFIED | 0 |
| `sql.cte.inventory_net_flow` | 1 | FULLY_VERIFIED | 0 |
| `sql.cte.logistics_depot_delay` | 1 | FULLY_VERIFIED | 0 |
| `sql.cte.monthly` | 4 | FULLY_VERIFIED | 0 |
| `sql.cte.order_line_reconciliation` | 1 | FULLY_VERIFIED | 0 |
| `sql.cte.saas_mrr_changes` | 1 | FULLY_VERIFIED | 0 |
| `sql.cte.session_funnel_completion` | 1 | FULLY_VERIFIED | 0 |
| `sql.dedup.education_grade_revisions` | 1 | FULLY_VERIFIED | 0 |
| `sql.dedup.latest` | 2 | FULLY_VERIFIED | 0 |
| `sql.dedup.payments_latest_profile` | 1 | FULLY_VERIFIED | 0 |
| `sql.dedup.refund_prefer_approved` | 1 | FULLY_VERIFIED | 0 |
| `sql.funnel.checkout_paid_session` | 1 | QUARANTINED | 0 |
| `sql.funnel.completion` | 3 | QUARANTINED | 0 |
| `sql.funnel.curriculum_gate_completion` | 1 | QUARANTINED | 0 |
| `sql.funnel.kyc_document_approval` | 1 | QUARANTINED | 0 |
| `sql.funnel.logistics_parcel_delivery` | 2 | QUARANTINED | 1 |
| `sql.funnel.parcel_exception_recovery` | 1 | QUARANTINED | 0 |
| `sql.funnel.saas_activation_payment` | 2 | FULLY_VERIFIED | 14 |
| `sql.funnel.support_resolution_chain` | 1 | QUARANTINED | 0 |
| `sql.joins.clinic_scheduled_clinician` | 1 | FULLY_VERIFIED | 0 |
| `sql.joins.education_completed_enrollment` | 1 | FULLY_VERIFIED | 0 |
| `sql.joins.logistics_final_leg` | 1 | FULLY_VERIFIED | 0 |
| `sql.joins.manufacturing_approved_supplier` | 1 | FULLY_VERIFIED | 0 |
| `sql.joins.multi` | 1 | FULLY_VERIFIED | 0 |
| `sql.joins.payments_country_transfer` | 1 | FULLY_VERIFIED | 0 |
| `sql.joins.saas_paid_invoices` | 1 | FULLY_VERIFIED | 0 |
| `sql.joins.simple` | 1 | FULLY_VERIFIED | 0 |
| `sql.retention.30_day` | 2 | FULLY_VERIFIED | 0 |
| `sql.retention.clinic_followup_window` | 1 | FULLY_VERIFIED | 0 |
| `sql.retention.media_week_two_return` | 1 | FULLY_VERIFIED | 0 |
| `sql.retention.saas_repeat_payment` | 1 | FULLY_VERIFIED | 0 |
| `sql.subqueries.customer_outreach` | 1 | FULLY_VERIFIED | 0 |
| `sql.subqueries.education_all_required` | 1 | FULLY_VERIFIED | 0 |
| `sql.subqueries.exists` | 2 | FULLY_VERIFIED | 0 |
| `sql.subqueries.payments_no_settlement` | 1 | FULLY_VERIFIED | 0 |
| `sql.subqueries.support_unresolved_reopen` | 1 | FULLY_VERIFIED | 0 |
| `sql.temporal.clinic_weekly_visits` | 1 | FULLY_VERIFIED | 0 |
| `sql.temporal.inventory_daily_stock` | 1 | FULLY_VERIFIED | 0 |
| `sql.temporal.logistics_service_level_as_of` | 1 | FULLY_VERIFIED | 0 |
| `sql.temporal.manufacturing_shift_downtime` | 1 | FULLY_VERIFIED | 0 |
| `sql.temporal.media_first_full_week_viewers` | 1 | FULLY_VERIFIED | 0 |
| `sql.temporal.monthly` | 5 | FULLY_VERIFIED | 0 |
| `sql.temporal.saas_account_snapshot` | 1 | FULLY_VERIFIED | 0 |
| `sql.temporal.saas_trial_activation` | 1 | FULLY_VERIFIED | 0 |
| `sql.windows.logistics_previous_stop` | 1 | FULLY_VERIFIED | 0 |
| `sql.windows.media_previous_play` | 1 | FULLY_VERIFIED | 0 |
| `sql.windows.payments_risk_rank` | 1 | FULLY_VERIFIED | 0 |
| `sql.windows.ranked` | 2 | FULLY_VERIFIED | 0 |
