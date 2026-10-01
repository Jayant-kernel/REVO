"""Oracle registry (Phase 4).

Every template must resolve to a known (oracle, version, strategy) triple
before verification. Unknown (template_id, version) pairs raise
``OracleUnknownError`` — never a silent generic fallback.

Version contract: every template version in the builtin task registry
must have an oracle entry. Entries in ``RETIRED_VERSIONS`` cover
template versions removed from the registry (their YAMLs are gone, so
no new task can reference them) but still replayable from historical
records — e.g. pilot-001 tasks pinned to v1 contracts. Retired entries
are explicit, never silent: anything registered that is neither current
nor retired is a consistency bug.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from . import oracle as oracle_fns
from .errors import OracleUnknownError
from .models import ExpectedResult

OracleFn = Callable[[Mapping[str, Any], Mapping[str, list[dict[str, Any]]]], ExpectedResult]


class OracleEntry:
    """Registry record: implementation + version + declared strategy."""

    __slots__ = ("fn", "oracle_version", "strategy")

    def __init__(self, fn: OracleFn, oracle_version: int, strategy: str) -> None:
        self.fn = fn
        self.oracle_version = oracle_version
        self.strategy = strategy


ORACLES: dict[tuple[str, int], OracleEntry] = {
    ("sql.joins.simple", 1): OracleEntry(
        oracle_fns.oracle_simple_joins, 1, "independent_join_aggregation"
    ),
    ("sql.joins.saas_paid_invoices", 1): OracleEntry(
        oracle_fns.oracle_saas_paid_invoices, 1, "independent_saas_invoice_selection"
    ),
    ("sql.joins.multi", 1): OracleEntry(
        oracle_fns.oracle_multi_joins, 1, "independent_multi_join_aggregation"
    ),
    ("sql.aggregation.grouped", 1): OracleEntry(
        oracle_fns.oracle_aggregation, 1, "independent_grouped_aggregation"
    ),
    ("sql.aggregation.grouped", 2): OracleEntry(
        oracle_fns.oracle_aggregation, 1, "independent_grouped_aggregation"
    ),
    ("sql.aggregation.payment_net_settled", 1): OracleEntry(
        oracle_fns.oracle_payment_net_settled, 1, "independent_payment_ledger_aggregation"
    ),
    ("sql.aggregation.support_sla_breaches", 1): OracleEntry(
        oracle_fns.oracle_support_sla_breaches, 1, "independent_support_sla_count"
    ),
    ("sql.cte.monthly", 1): OracleEntry(oracle_fns.oracle_cte, 1, "independent_cte_aggregation"),
    ("sql.cte.monthly", 2): OracleEntry(oracle_fns.oracle_cte, 1, "independent_cte_aggregation"),
    ("sql.cte.monthly", 3): OracleEntry(oracle_fns.oracle_cte, 1, "independent_cte_aggregation"),
    ("sql.cte.monthly", 4): OracleEntry(oracle_fns.oracle_cte, 1, "independent_cte_aggregation"),
    ("sql.subqueries.exists", 1): OracleEntry(
        oracle_fns.oracle_subqueries, 1, "independent_exists_subquery"
    ),
    ("sql.subqueries.exists", 2): OracleEntry(
        oracle_fns.oracle_subqueries, 1, "independent_exists_subquery"
    ),
    ("sql.windows.ranked", 1): OracleEntry(
        oracle_fns.oracle_windows, 1, "independent_window_computation"
    ),
    ("sql.windows.ranked", 2): OracleEntry(
        oracle_fns.oracle_windows, 2, "independent_window_computation"
    ),
    ("sql.temporal.monthly", 1): OracleEntry(
        oracle_fns.oracle_temporal, 1, "independent_temporal_aggregation"
    ),
    ("sql.temporal.monthly", 2): OracleEntry(
        oracle_fns.oracle_temporal, 1, "independent_temporal_aggregation"
    ),
    ("sql.temporal.monthly", 3): OracleEntry(
        oracle_fns.oracle_temporal, 1, "independent_temporal_aggregation"
    ),
    ("sql.temporal.monthly", 4): OracleEntry(
        oracle_fns.oracle_temporal, 1, "independent_temporal_aggregation"
    ),
    ("sql.temporal.monthly", 5): OracleEntry(
        oracle_fns.oracle_temporal, 1, "independent_temporal_aggregation"
    ),
    ("sql.dedup.latest", 1): OracleEntry(oracle_fns.oracle_dedup, 1, "independent_dedup_selection"),
    ("sql.dedup.latest", 2): OracleEntry(oracle_fns.oracle_dedup, 1, "independent_dedup_selection"),
    ("sql.dedup.education_grade_revisions", 1): OracleEntry(
        oracle_fns.oracle_education_grade_revisions,
        1,
        "independent_valid_grade_revision_selection",
    ),
    ("sql.retention.30_day", 1): OracleEntry(
        oracle_fns.oracle_retention, 1, "independent_aggregation"
    ),
    ("sql.retention.30_day", 2): OracleEntry(
        oracle_fns.oracle_retention, 2, "independent_aggregation"
    ),
    ("sql.funnel.completion", 1): OracleEntry(
        oracle_fns.oracle_funnel, 1, "independent_funnel_ordering"
    ),
    ("sql.funnel.completion", 2): OracleEntry(
        oracle_fns.oracle_funnel, 1, "independent_funnel_ordering"
    ),
    ("sql.funnel.completion", 3): OracleEntry(
        oracle_fns.oracle_funnel, 2, "independent_funnel_ordering"
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
#: entries are retained for historical replay. A retired version can
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
