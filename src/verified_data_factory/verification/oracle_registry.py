"""Oracle registry (Phase 4).

Every template must resolve to a known (oracle, version, strategy) triple
before verification. Unknown (template_id, version) pairs raise
``OracleUnknownError`` — never a silent generic fallback.

Version contract: every template version in the builtin task registry
must have an oracle entry. Entries in ``RETIRED_VERSIONS`` cover
template versions removed from the registry (their YAMLs are gone, so
no new task can reference them) but still replayable from historical
records — e.g. pilot-001 tasks pinned to v1 contracts. Resolution is current
re-adjudication, not historical semantic reproduction: the five retired entries
share typed implementations and identify their current advanced versions. Retired entries
are explicit, never silent: anything registered that is neither current
nor retired is a consistency bug.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from . import business_oracles
from . import oracle as oracle_fns
from .errors import OracleUnknownError
from .models import ExpectedResult
from .qualification.language_titles_profile import expected as language_titles_expected
from .qualification.lowest_quote_profile import expected as lowest_quote_expected
from .qualification.pareto_shipping_profile import expected as pareto_shipping_expected
from .qualification.queue_batches_profile import expected as queue_batches_expected
from .qualification.renewal_coverage_profile import expected as renewal_coverage_expected

OracleFn = Callable[[Mapping[str, Any], Mapping[str, list[dict[str, Any]]]], ExpectedResult]


class OracleEntry:
    """Registry record: implementation + version + declared strategy."""

    __slots__ = ("fn", "oracle_version", "strategy")

    def __init__(self, fn: OracleFn, oracle_version: int, strategy: str) -> None:
        self.fn = fn
        self.oracle_version = oracle_version
        self.strategy = strategy


ORACLES: dict[tuple[str, int], OracleEntry] = {
    ("sql.retention.renewal_coverage", 1): OracleEntry(renewal_coverage_expected, 1, "authored_renewal_interval_coverage"),
    ("sql.windows.queue_batches", 1): OracleEntry(queue_batches_expected, 1, "authored_balanced_ntile_batches"),
    ("sql.joins.requested_language_titles", 1): OracleEntry(language_titles_expected, 1, "authored_requested_language_titles"),
    ("sql.subqueries.pareto_shipping", 1): OracleEntry(pareto_shipping_expected, 1, "authored_pareto_shipping_v1"),
    ("sql.dedup.lowest_quote", 1): OracleEntry(lowest_quote_expected, 1, "authored_lowest_quote_v1"),
    **{(template_id, 1): OracleEntry(business_oracles.expansion_total, 2, "independent_event_ledger_reconciliation") for template_id in (
        "sql.joins.payments_country_transfer", "sql.joins.clinic_scheduled_clinician", "sql.joins.manufacturing_approved_supplier", "sql.joins.education_completed_enrollment", "sql.aggregation.manufacturing_line_scrap", "sql.cte.saas_mrr_changes", "sql.cte.logistics_depot_delay", "sql.subqueries.payments_no_settlement", "sql.subqueries.support_unresolved_reopen", "sql.windows.payments_risk_rank", "sql.windows.logistics_previous_stop", "sql.temporal.saas_trial_activation", "sql.temporal.inventory_daily_stock", "sql.dedup.refund_prefer_approved", "sql.dedup.payments_latest_profile", "sql.retention.media_week_two_return", "sql.retention.clinic_followup_window",
    )},
    ("sql.funnel.saas_activation_payment", 2): OracleEntry(business_oracles.saas_activation_payment, 4, "differential_saas_activation_state_machine"),
    ("sql.funnel.logistics_parcel_delivery", 1): OracleEntry(business_oracles.logistics_parcel_delivery, 3, "differential_logistics_delivery_state_machine"),
    ("sql.funnel.logistics_parcel_delivery", 2): OracleEntry(business_oracles.logistics_parcel_delivery_v2, 4, "bounded_logistics_delivery_consecutive_state_machine_v2"),
    ("sql.joins.logistics_final_leg", 1): OracleEntry(business_oracles.final_leg, 3, "independent_final_leg_lookup"),
    ("sql.cte.inventory_net_flow", 1): OracleEntry(business_oracles.net_flow, 2, "independent_inventory_reconciliation"),
    ("sql.cte.inventory_net_flow", 2): OracleEntry(business_oracles.net_flow, 2, "independent_inventory_reconciliation"),
    ("sql.subqueries.education_all_required", 1): OracleEntry(business_oracles.all_required, 2, "independent_required_course_sets"),
    ("sql.windows.media_previous_play", 1): OracleEntry(business_oracles.previous_play, 3, "independent_playback_history"),
    ("sql.temporal.clinic_weekly_visits", 1): OracleEntry(business_oracles.weekly_visits, 2, "independent_monday_calendar"),
    ("sql.temporal.media_first_full_week_viewers", 1): OracleEntry(business_oracles.first_full_week_viewers, 2, "independent_first_seven_calendar_days"),
    ("sql.temporal.manufacturing_shift_downtime", 1): OracleEntry(business_oracles.manufacturing_shift_downtime, 2, "independent_closed_interval_duration"),
    ("sql.temporal.logistics_service_level_as_of", 1): OracleEntry(business_oracles.logistics_service_level_as_of, 2, "independent_latest_tracking_as_of"),
    ("sql.temporal.saas_account_snapshot", 1): OracleEntry(business_oracles.saas_account_snapshot, 2, "independent_latest_account_revision_as_of"),
    ("sql.retention.saas_repeat_payment", 1): OracleEntry(business_oracles.repeat_payment, 2, "independent_first_paid_cohort"),
    ("sql.funnel.support_resolution_chain", 1): OracleEntry(business_oracles.resolution_chain, 2, "independent_support_state_machine"),
    ("sql.aggregation.warehouse_throughput", 1): OracleEntry(business_oracles.warehouse_throughput, 2, "independent_having_threshold"),
    ("sql.aggregation.warehouse_throughput", 2): OracleEntry(business_oracles.warehouse_throughput, 2, "independent_having_threshold"),
    ("sql.aggregation.top_category_sales", 1): OracleEntry(business_oracles.top_category_sales, 3, "independent_top_k_limit"),
    ("sql.aggregation.fulfillment_sla_dashboard", 1): OracleEntry(business_oracles.fulfillment_sla_dashboard, 2, "independent_fulfillment_sla_dashboard"),
    ("sql.aggregation.product_unique_conversion", 1): OracleEntry(business_oracles.product_unique_conversion, 2, "independent_unique_product_conversion"),
    ("sql.cte.order_line_reconciliation", 1): OracleEntry(business_oracles.order_line_reconciliation, 2, "independent_order_line_reconciliation"),
    ("sql.cte.category_descendant_sales", 1): OracleEntry(business_oracles.category_descendant_sales, 2, "independent_category_descendant_sales"),
    ("sql.cte.session_funnel_completion", 1): OracleEntry(business_oracles.session_funnel_completion, 2, "independent_session_funnel_completion"),
    ("sql.cte.customer_first_month_repeat", 1): OracleEntry(business_oracles.customer_first_month_repeat, 2, "independent_first_month_repeat"),
    ("sql.subqueries.customer_outreach", 1): OracleEntry(business_oracles.customer_outreach, 2, "independent_union_dedup"),
    ("sql.funnel.checkout_paid_session", 1): OracleEntry(business_oracles.checkout_paid_session, 2, "independent_session_checkout_payment"),
    ("sql.funnel.kyc_document_approval", 1): OracleEntry(business_oracles.kyc_document_approval, 2, "independent_kyc_requirement_state_machine"),
    ("sql.funnel.parcel_exception_recovery", 1): OracleEntry(business_oracles.parcel_exception_recovery, 2, "independent_latest_exception_recovery"),
    ("sql.funnel.curriculum_gate_completion", 1): OracleEntry(business_oracles.curriculum_gate_completion, 2, "independent_curriculum_stage_state_machine"),
    ("sql.joins.simple", 1): OracleEntry(
        oracle_fns.oracle_simple_joins, 2, "independent_join_aggregation"
    ),
    ("sql.joins.saas_paid_invoices", 1): OracleEntry(
        oracle_fns.oracle_saas_paid_invoices, 3, "independent_saas_invoice_selection"
    ),
    ("sql.joins.multi", 1): OracleEntry(
        oracle_fns.oracle_multi_joins, 2, "independent_multi_join_aggregation"
    ),
    ("sql.aggregation.grouped", 1): OracleEntry(
        oracle_fns.oracle_aggregation, 2, "independent_grouped_aggregation"
    ),
    ("sql.aggregation.grouped", 2): OracleEntry(
        oracle_fns.oracle_aggregation, 2, "independent_grouped_aggregation"
    ),
    ("sql.aggregation.payment_net_settled", 1): OracleEntry(
        oracle_fns.oracle_payment_net_settled, 2, "independent_payment_ledger_aggregation"
    ),
    ("sql.aggregation.support_sla_breaches", 1): OracleEntry(
        oracle_fns.oracle_support_sla_breaches, 2, "independent_support_sla_count"
    ),
    ("sql.cte.monthly", 1): OracleEntry(oracle_fns.oracle_cte, 2, "independent_cte_aggregation"),
    ("sql.cte.monthly", 2): OracleEntry(oracle_fns.oracle_cte, 2, "independent_cte_aggregation"),
    ("sql.cte.monthly", 3): OracleEntry(oracle_fns.oracle_cte, 2, "independent_cte_aggregation"),
    ("sql.cte.monthly", 4): OracleEntry(oracle_fns.oracle_cte, 2, "independent_cte_aggregation"),
    ("sql.subqueries.exists", 1): OracleEntry(
        oracle_fns.oracle_subqueries, 3, "independent_exists_subquery"
    ),
    ("sql.subqueries.exists", 2): OracleEntry(
        oracle_fns.oracle_subqueries, 3, "independent_exists_subquery"
    ),
    ("sql.windows.ranked", 1): OracleEntry(
        oracle_fns.oracle_windows, 3, "independent_window_computation"
    ),
    ("sql.windows.ranked", 2): OracleEntry(
        oracle_fns.oracle_windows, 3, "independent_window_computation"
    ),
    ("sql.temporal.monthly", 1): OracleEntry(
        oracle_fns.oracle_temporal, 2, "independent_temporal_aggregation"
    ),
    ("sql.temporal.monthly", 2): OracleEntry(
        oracle_fns.oracle_temporal, 2, "independent_temporal_aggregation"
    ),
    ("sql.temporal.monthly", 3): OracleEntry(
        oracle_fns.oracle_temporal, 2, "independent_temporal_aggregation"
    ),
    ("sql.temporal.monthly", 4): OracleEntry(
        oracle_fns.oracle_temporal, 2, "independent_temporal_aggregation"
    ),
    ("sql.temporal.monthly", 5): OracleEntry(
        oracle_fns.oracle_temporal, 2, "independent_temporal_aggregation"
    ),
    ("sql.dedup.latest", 1): OracleEntry(oracle_fns.oracle_dedup, 2, "independent_dedup_selection"),
    ("sql.dedup.latest", 2): OracleEntry(oracle_fns.oracle_dedup, 2, "independent_dedup_selection"),
    ("sql.dedup.education_grade_revisions", 1): OracleEntry(
        oracle_fns.oracle_education_grade_revisions,
        2,
        "independent_valid_grade_revision_selection",
    ),
    ("sql.dedup.education_grade_revisions", 2): OracleEntry(
        oracle_fns.oracle_immutable_education_grade_revisions,
        3,
        "independent_immutable_valid_grade_revision_selection",
    ),
    ("sql.retention.30_day", 1): OracleEntry(
        oracle_fns.oracle_retention, 2, "independent_aggregation"
    ),
    ("sql.retention.30_day", 2): OracleEntry(
        oracle_fns.oracle_retention, 3, "independent_aggregation"
    ),
    ("sql.funnel.completion", 1): OracleEntry(
        oracle_fns.oracle_funnel, 2, "independent_funnel_ordering"
    ),
    ("sql.funnel.completion", 2): OracleEntry(
        oracle_fns.oracle_funnel, 2, "independent_funnel_ordering"
    ),
    ("sql.funnel.completion", 3): OracleEntry(
        oracle_fns.oracle_funnel, 3, "independent_funnel_ordering"
    ),
}


def get_oracle(template_id: str, template_version: int) -> OracleEntry:
    """Resolve the oracle triple or raise ``OracleUnknownError``."""
    try:
        return ORACLES[(template_id, template_version)]
    except KeyError as exc:
        raise OracleUnknownError(
            f"no oracle registered for {template_id!r} version {template_version}"
        ) from exc


def known_templates() -> list[tuple[str, int]]:
    """All registered (template_id, version) pairs, sorted."""
    return sorted(ORACLES)


#: Template versions removed from the builtin registry whose oracle
#: entries are retained for historical task re-adjudication. A retired version can
#: never be generated (the template registry no longer lists it) but
#: remains resolvable here so pre-existing records stay verifiable.
RETIRED_VERSIONS: frozenset[tuple[str, int]] = frozenset(
    {
        ("sql.aggregation.grouped", 1),
        ("sql.cte.monthly", 1),
        ("sql.dedup.latest", 1),
        ("sql.funnel.completion", 1),
        ("sql.temporal.monthly", 1),
    }
)


def is_retired_version(template_id: str, template_version: int) -> bool:
    """True when a version is retired: replayable, but not generatable."""
    return (template_id, template_version) in RETIRED_VERSIONS
