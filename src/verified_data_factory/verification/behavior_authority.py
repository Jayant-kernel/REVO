"""Versioned public declarations for mutation coverage, independent of operators.

An opaque instruction is an outstanding semantic obligation, not inferred intent.
No operator earns attribution merely because its name resembles a requirement.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel

from verified_data_factory.task_engine.errors import RegistryError
from verified_data_factory.task_engine.fixtures import generate_fixture_tables
from verified_data_factory.task_engine.instruction import (
    build_instruction_context,
    render_instruction,
)
from verified_data_factory.task_engine.models import TaskInstance
from verified_data_factory.task_engine.registry import load_builtin_registry

from .qualification.delivery_profiles import PROFILE_IDS, get_profile, raw_key

BEHAVIOR_MAP_VERSION: Literal[1] = 1

SUPPORTED_GRANULAR = {
    *PROFILE_IDS,
    ("sql.dedup.lowest_quote", 1),
    ("sql.funnel.saas_activation_payment", 2),
    ("sql.aggregation.manufacturing_line_scrap", 1),
    ("sql.aggregation.fulfillment_sla_dashboard", 1),
    ("sql.joins.saas_paid_invoices", 1),
    ("sql.subqueries.exists", 2),
    ("sql.joins.logistics_final_leg", 1),
    ("sql.temporal.clinic_weekly_visits", 1),
    ("sql.retention.saas_repeat_payment", 1),
    ("sql.cte.order_line_reconciliation", 1),
    ("sql.windows.media_previous_play", 1),
    ("sql.aggregation.support_sla_breaches", 1),
    ("sql.dedup.education_grade_revisions", 2),
    ("sql.aggregation.warehouse_throughput", 2),
    ("sql.subqueries.education_all_required", 1),
    ("sql.cte.inventory_net_flow", 2),
}

# Exact public prose, not an interpreter for other contracts' generic intent.
SAAS_CLAUSES = {
    "year": ("year", "Return eligible completed SaaS activation-payment funnel value by segment in {year}."),
    "ordered_steps": ("ordered_steps", "For each entity, order records by occurred_at then sequence ascending; a funnel completes when signup, trial, activation, and payment occur in that order, with the first matching record advancing each step."),
    "first_matching": ("first_matching", "with the first matching record advancing each step."),
    "timestamp_sequence": ("same_timestamp_policy", "order records by occurred_at then sequence ascending"),
    "scope": ("in_scope_statuses", "Only rows whose status is one of those four funnel steps in {year} are in scope."),
    "payment_sum": ("completion_amount", "For each completed entity, use the amount on its matched payment event; sum those amounts by segment."),
    "sum_by_segment": ("group_by_segment", "sum those amounts by segment."),
    "matched_payment": ("repeat_policy", "use the amount on its matched payment event"),
    "zero_incomplete": ("zero_incomplete", "Include every segment with in-scope rows, returning zero total_amount when none completes"),
    "ascending": ("order_by", "order segments ascending."),
    "ignore_unexpected": ("consecutiveness", "Rows that do not match the next expected step are ignored: they neither advance nor reset progress."),
    "entity_group": ("entity_group", "Each entity keeps one segment across all its rows, so a completion counts toward that entity's segment."),
    "unique_order": ("tie_uniqueness", "No two rows of the same entity share both occurred_at and sequence."),
}


class PublicBehavior(BaseModel):
    model_config = {"frozen": True, "extra": "forbid"}

    rule_id: str
    origin: Literal["requirements", "instruction", "schema"]
    kind: Literal["semantic", "input_domain", "structural"]
    declaration_json: str
    proof_key: str = ""
    source_clause: str = ""


class PublicBehaviorMap(BaseModel):
    model_config = {"frozen": True, "extra": "forbid"}

    schema_version: Literal[1] = BEHAVIOR_MAP_VERSION
    contract_id: str
    contract_version: int
    declaration_sha256: str = ""
    rules: tuple[PublicBehavior, ...] = ()
    task_matches_public_contract: bool = False
    blocked_reason: str = ""
    granular: bool = False

    @property
    def semantic_rule_ids(self) -> tuple[str, ...]:
        return tuple(rule.rule_id for rule in self.rules if rule.kind == "semantic")

    @property
    def domain_rule_ids(self) -> tuple[str, ...]:
        return tuple(rule.rule_id for rule in self.rules if rule.kind == "input_domain")

    @property
    def structural_rule_ids(self) -> tuple[str, ...]:
        return tuple(rule.rule_id for rule in self.rules if rule.kind == "structural")


def _encode(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def public_behavior_map(task: TaskInstance) -> PublicBehaviorMap:
    """Resolve exact builtin identity; callers cannot shrink public obligations.

    Schema types/nullability are domain obligations and need separate rejection
    proofs. Free-form requirements remain semantic unless a future explicit public
    map declares otherwise; guessing a domain disposition would erase coverage.
    """
    identity = {"contract_id": task.template_id, "contract_version": task.template_version}
    try:
        template = load_builtin_registry().get(task.template_id, task.template_version)
    except RegistryError:
        return PublicBehaviorMap(**identity, blocked_reason="unknown public contract/version")
    rules = [
        PublicBehavior(
            rule_id=key, origin="requirements", kind="semantic", declaration_json=_encode(value)
        )
        for key, value in sorted(template.requirements.items())
    ]
    rules.append(PublicBehavior(
        rule_id="instruction:declared", origin="instruction", kind="semantic",
        declaration_json=_encode(template.instruction_template),
    ))
    rules.append(PublicBehavior(
        rule_id="instruction:edge_cases", origin="instruction", kind="semantic",
        declaration_json=_encode(template.edge_cases),
    ))
    granular = (task.template_id, task.template_version) in SUPPORTED_GRANULAR
    if granular:
        pair = (task.template_id, task.template_version)
        followup = get_profile(*pair)
        domain_keys = followup.DOMAIN_KEYS if followup is not None else {
            ("sql.dedup.lowest_quote", 1): {"input_domain_rules"},
            ("sql.funnel.saas_activation_payment", 2): {"tie_uniqueness", "null_handling"},
            ("sql.aggregation.manufacturing_line_scrap", 1): {"null_handling"},
            ("sql.aggregation.fulfillment_sla_dashboard", 1): set(),
            ("sql.joins.saas_paid_invoices", 1): {"null_semantics"},
            ("sql.subqueries.exists", 2): set(),
            ("sql.joins.logistics_final_leg", 1): set(),
            ("sql.temporal.clinic_weekly_visits", 1): set(),
            ("sql.retention.saas_repeat_payment", 1): set(),
            ("sql.cte.order_line_reconciliation", 1): set(),
            ("sql.windows.media_previous_play", 1): set(),
            ("sql.aggregation.support_sla_breaches", 1): set(),
            ("sql.dedup.education_grade_revisions", 2): {"immutable_valid_revision_identity"},
            ("sql.aggregation.warehouse_throughput", 2): {"null_handling"},
            ("sql.subqueries.education_all_required", 1): set(),
            ("sql.cte.inventory_net_flow", 2): set(),
        }[pair]
        rules = [PublicBehavior(
            rule_id=key, origin="requirements",
            kind="input_domain" if key in domain_keys else "semantic",
            declaration_json=_encode(value), proof_key="null_handling" if key == "null_semantics" and followup is None else key,
            source_clause=f"requirements.{key}={_encode(value)}",
        ) for key, value in sorted(template.requirements.items())]
        if followup is not None:
            clauses = followup.CLAUSES
        elif pair == ("sql.dedup.lowest_quote", 1):
            clauses = {
                "columns": ("output_columns", "Return {output_columns}"),
                "types": ("output_types", "with types VARCHAR,VARCHAR,INTEGER"),
                "order": ("order_by", "ordered by part ascending."),
                "cents": ("price_type", "integer currency cents"),
                "range": ("input_domain_rules", "price_cents is nullable and otherwise in [0,2147483647]."),
                "text": ("part_type", "All other fields are nonnull text"),
                "empty_text": ("empty_text", "including empty text"),
                "no_unique": ("exact_repeats", "no uniqueness is assumed."),
                "part": ("duplicate_key", "For each part select minimum nonnull price"),
                "winner": ("winner_rule", "minimum nonnull price"),
                "tie": ("tie_break", "then lexicographically smallest supplier"),
                "binary": ("binary_text", "under DuckDB default binary text ordering."),
                "repeat": ("exact_repeats", "Exact repeats and tied identical projected winners produce one row, not multiple rows."),
                "unknown": ("null_prices", "NULL price means unknown and is excluded before selection"),
                "all_null": ("null_prices", "all-NULL parts are omitted."),
                "empty": ("empty_result", "Empty input gives empty output."),
                "no_scope": ("no_scope", "No time, year, status, or latest-row filter."),
            }
        elif pair == ("sql.cte.inventory_net_flow", 2):
            clauses = {
                "year": ("year", "Reconcile warehouse stock movement for {year}"),
                "receipts": ("objective", "posted receipts add units"),
                "issues": ("objective", "posted issues subtract units."),
                "signed": ("signed_units", "Signed negative units are corrections."),
                "bag": ("count_semantics", "Each posted input row contributes once"),
                "repeat": ("count_semantics", "even when movement_id or the entire payload repeats"),
                "no_id_uniqueness": ("count_semantics", "movement_id does not imply uniqueness or de-duplication."),
                "columns": ("output_columns", "Return warehouse and net_units"),
                "order": ("order_by", "ordered by warehouse"),
                "zero": ("empty_group_behavior", "including zero net flow"),
                "one_side": ("unmatched_behavior", "warehouses appearing on only one side."),
                "status": ("issue_scope", "Exclude unposted"),
                "excluded_year": ("year", "out-of-year movements."),
            }
        elif pair == ("sql.aggregation.warehouse_throughput", 2):
            clauses = {
                "sum": ("objective", "sum units per warehouse"),
                "posted": ("status_filter", "for '{status_filter}' loads"),
                "year": ("year", "in {year}."),
                "bag": ("count_semantics", "Each posted input row contributes its units once"),
                "nonnull": ("null_handling", "units are non-null."),
                "threshold": ("min_total_units", "Keep only warehouses whose summed units reach at least the threshold"),
                "aggregate_having": ("having_structure", "MUST express that group-level condition with a HAVING clause on the aggregate (not a WHERE on individual rows)."),
                "columns": ("output_columns", "Return exactly warehouse and total_units"),
                "order": ("order_by", "ordered by warehouse."),
                "empty": ("empty_group_behavior", "Warehouses without qualifying loads produce no row"),
                "values": ("zero_negative", "Handle zero and negative unit groups"),
            }
        elif pair == ("sql.dedup.education_grade_revisions", 2):
            clauses = {
                "winner": ("winner_rule", "from the most recently recorded valid revision."),
                "valid": ("canceled_policy", "Ignore cancelled corrections before choosing a winner."),
                "pair": ("duplicate_key", "for each student and course"),
                "tie": ("tie_break", "use the higher revision_id."),
                "empty": ("no_valid_policy", "Leave out student-course pairs with no valid revision."),
                "identity": ("immutable_valid_revision_identity", "equal student_id, course_id, recorded_at, and revision_id identify an immutable revision whose grade must agree"),
                "conflict": ("immutable_valid_revision_identity", "reject conflicting valid grades at that identity."),
                "repeat": ("exact_repeats", "Exact repeated valid rows are allowed and do not create another winner."),
                "columns": ("output_columns", "Return student_id, course_id, grade, recorded_at, and revision_id"),
                "order": ("order_by", "ordered by student_id and course_id."),
            }
        elif pair == ("sql.aggregation.support_sla_breaches", 1):
            clauses = {
                "year": ("year", "For support tickets opened in {year}"),
                "late": ("objective", "count the tickets resolved after their SLA deadline"),
                "group": ("group_by", "grouped by team and priority."),
                "null": ("null_handling", "An unresolved ticket is not a resolved breach"),
                "equal": ("boundary_policy", "a resolution exactly at the deadline is on time."),
                "columns": ("output_columns", "Return team, priority, and breach_count"),
                "order": ("order_by", "in team and priority order."),
                "empty": ("empty_group_behavior", "Omit groups with no qualifying tickets."),
            }
        elif pair == ("sql.windows.media_previous_play", 1):
            clauses = {
                "completed": ("status_filter", "For completed playbacks"),
                "year": ("year", "in {year}"),
                "previous": ("objective", "find the previous completed playback"),
                "title": ("partition_by", "of the same title"),
                "viewer": ("title", "by the same viewer"),
                "history": ("running_order", "Order history by played_at then play_id"),
                "tie": ("tie_policy", "then play_id"),
                "partial": ("status_filter", "partial plays do not participate."),
                "columns": ("output_columns", "Return play_id and previous_play_id"),
                "order": ("order_by", "ordered by play_id."),
                "first": ("null_ordering", "The first playback in each history has NULL previous_play_id."),
                "bag": ("bag", "For completed playbacks"),
            }
        elif pair == ("sql.cte.order_line_reconciliation", 1):
            clauses = {
                "product": ("product", "sum quantity * unit_price_cents per order line."),
                "status": ("status_filter", "For completed orders"),
                "year": ("year", "in {year}"),
                "mismatch": ("objective", "return only orders whose header_total_cents differs from their line total"),
                "columns": ("output_columns", "with order_id, header_total_cents, and line_total_cents"),
                "order": ("order_by", "ordered by order_id."),
                "empty": ("unmatched_behavior", "completed order with no lines as line_total_cents zero"),
                "header_bag": ("bag", "For completed orders"),
                "line_bag": ("line_bag", "per order line."),
            }
        elif pair == ("sql.retention.saas_repeat_payment", 1):
            clauses = {
                "cohort": ("cohort_definition", "Use the first ever paid date, including prior years when assigning the cohort."),
                "year": ("year", "first paid an invoice in {year}"),
                "later": ("repeated_event_policy", "paid again on a later date"),
                "window": ("retention_window_days", "within {retention_window_days} days"),
                "same_day": ("repeated_event_policy", "Same-day invoices are not returns"),
                "day30": ("boundary_policy", "day 30 qualifies"),
                "day31": ("retention_window_days", "day 31 does not."),
                "status": ("qualifying_event", "Ignore unpaid invoices"),
                "null": ("null_date", "NULL paid dates."),
                "once": ("once", "Return each retained account_id once"),
                "order": ("order_by", "in ascending order."),
            }
        elif pair == ("sql.temporal.clinic_weekly_visits", 1):
            clauses = {
                "count": ("objective", "Count completed visits"),
                "status": ("completed", "noncompleted visits are excluded."),
                "year": ("year", "starting in {year}"),
                "week": ("month_definition", "Weeks start Monday at midnight"),
                "date": ("output_columns", "as an ISO DATE week_start"),
                "previous_year": ("prior_year_monday", "even when it falls in the previous year."),
                "null_start": ("null_start", "NULL start times"),
                "columns": ("output_columns", "Return clinic, week_start, visit_count"),
                "order": ("order_by", "ordered by clinic then week_start."),
                "empty": ("omit_empty", "Omit empty groups."),
            }
        elif pair == ("sql.joins.logistics_final_leg", 1):
            clauses = {
                "year": ("year", "For parcels delivered in {year}"),
                "declared_leg": ("declared_leg", "the declared final leg."),
                "carrier": ("carrier_correlation", "the depot and carrier responsible"),
                "bag": ("bag", "For parcels delivered"),
                "columns": ("output_columns", "Return shipment_id, depot, carrier_name"),
                "order": ("order_by", "ordered by shipment_id."),
                "missing": ("unmatched_behavior", "Omit parcels whose final leg or carrier is missing."),
                "null_delivery": ("null_delivery", "A NULL delivery date means the parcel has not been delivered."),
            }
        elif pair == ("sql.joins.saas_paid_invoices", 1):
            clauses = {
                "year": ("year", "List the invoices issued in {year}"),
                "paid": ("status_filter", "that are marked paid"),
                "active": ("account_status_filter", "whose current status is active"),
                "matching": ("objective", "belong to an account"),
                "columns": ("output_columns", "Show invoice_id, account_name, and amount_cents"),
                "bag": ("multiplicity", "List the invoices"),
                "minor_units": ("minor_units", "Amounts are integer minor units"),
                "order": ("order_by", "in invoice_id order"),
                "unmatched": ("unmatched_behavior", "an account with no invoices has no row."),
            }
        elif pair == ("sql.subqueries.education_all_required", 1):
            clauses = {
                "every_course": ("objective", "passed every required course in their program"),
                "threshold": ("threshold_operator", "score of at least {passing_score}."),
                "attempts": ("exists_semantics", "Any passing attempt suffices"),
                "failed": ("failed_attempts", "failed or NULL-scored attempts do not erase a pass."),
                "requirements": ("required_set", "Duplicate requirements"),
                "repeats": ("exists_semantics", "repeat attempts count only once per course."),
                "empty": ("no_match_behavior", "Exclude programs with no requirements"),
                "optional": ("optional_courses", "optional courses cannot replace missing requirements."),
                "columns": ("output_columns", "Return student_id"),
                "order": ("order_by", "in ascending order."),
            }
        elif pair == ("sql.subqueries.exists", 2):
            clauses = {
                "correlation": ("objective", "Which customers placed at least one"),
                "completed": ("status_filter", "completed order"),
                "threshold": ("threshold_operator", "over {min_amount}"),
                "year": ("year", "during {year}"),
                "columns": ("output_columns", "Return customer_id and name"),
                "bag": ("customer_bag", "Return customer_id and name"),
                "order": ("order_by", "in customer_id order"),
                "excluded": ("no_match_behavior", "Do not include customers who have no such order"),
                "orderless": ("no_match_behavior", "including customers with no orders."),
            }
        elif pair == ("sql.aggregation.fulfillment_sla_dashboard", 1):
            clauses = {
                "year": ("year", "fulfillments shipped in the year"),
                "status": ("status_filter", "Include only '{status_filter}' fulfillments"),
                "nonnull_delivery": ("null_handling", "with a non-null delivery timestamp"),
                "counts": ("count_semantics", "Return warehouse, delivered_fulfillments, and on_time_fulfillments"),
                "deadline": ("deadline_inclusive", "delivered_at is no later than promised_at"),
                "order": ("order_by", "Order by warehouse."),
                "exclude_cancelled": ("status_filter", "Exclude cancelled"),
                "exclude_unresolved": ("null_handling", "unresolved"),
                "exclude_other_year": ("year", "out-of-year fulfillments"),
            }
        elif pair == ("sql.funnel.saas_activation_payment", 2):
            clauses = SAAS_CLAUSES
        elif pair == ("sql.aggregation.manufacturing_line_scrap", 1):
            clauses = {
                "sum": ("objective", "Aggregate eligible production scrap amount"),
                "eligible": ("empty_group_behavior", "eligible production scrap"),
                "line": ("group_by", "amount by line"),
                "year": ("year", "in {year}"),
                "ascending": ("order_by", "ordered by line."),
            }
        else:
            raise ValueError("unsupported granular contract/version")
        normalized = " ".join(template.instruction_template.split())
        for name, (proof, clause) in clauses.items():
            if clause not in normalized:
                raise ValueError("version-bound public clause changed; revise granular map")
            clause_kind: Literal["semantic", "input_domain", "structural"] = "semantic"
            if proof == "having_structure" or (followup is not None and proof in followup.STRUCTURAL_KEYS):
                clause_kind = "structural"
            elif (followup is not None and proof in followup.DOMAIN_KEYS) or (pair == ("sql.dedup.lowest_quote", 1) and proof in {"input_domain_rules", "price_type", "part_type", "supplier_type"}) or proof in {"entity_group", "tie_uniqueness", "immutable_valid_revision_identity"} or (
                pair == ("sql.aggregation.warehouse_throughput", 2) and proof == "null_handling"
            ):
                clause_kind = "input_domain"
            rules.append(PublicBehavior(
                rule_id=f"instruction:{name}", origin="instruction",
                kind=clause_kind,
                declaration_json=_encode(clause), source_clause=clause, proof_key=proof,
            ))
        edge_proofs = {"ties": "same_timestamp_policy", "duplicates": "repeat_policy",
                       "ineligible_rows": "in_scope_statuses" if pair == ("sql.funnel.saas_activation_payment", 2) else "empty_group_behavior",
                       "zero_values": "zero_values", "year_boundary": "year"}
        if followup is not None:
            edge_proofs = followup.EDGE_PROOFS
        if pair == ("sql.dedup.lowest_quote", 1):
            edge_proofs = {"null_values": "null_prices", "ties": "tie_break", "duplicates": "exact_repeats",
                           "zero_values": "zero_values", "empty_result": "empty_result"}
        if task.template_id == "sql.aggregation.fulfillment_sla_dashboard":
            edge_proofs.update({"null_values": "null_handling", "ineligible_rows": "status_filter"})
        if pair == ("sql.joins.saas_paid_invoices", 1):
            edge_proofs = {"missing_relationships": "join_type", "account_without_invoices": "unmatched_behavior",
                           "inactive_accounts": "account_status_filter", "invoice_year_boundary": "year"}
        elif pair == ("sql.subqueries.exists", 2):
            edge_proofs = {"missing_relationships": "no_match_behavior"}
        elif pair == ("sql.subqueries.education_all_required", 1):
            edge_proofs = {"null_values": "null_score", "duplicates": "required_set",
                           "multiple_matching_rows": "exists_semantics", "missing_relationships": "correlation"}
        elif pair == ("sql.joins.logistics_final_leg", 1):
            edge_proofs = {"missing_relationships": "unmatched_behavior", "null_values": "null_delivery"}
        elif pair == ("sql.temporal.clinic_weekly_visits", 1):
            edge_proofs = {"null_values": "null_start", "same_day_events": "objective", "window_end_boundary": "window_end"}
        elif pair == ("sql.retention.saas_repeat_payment", 1):
            edge_proofs = {"null_values": "null_date", "same_day_events": "repeated_event_policy",
                           "retention_boundaries": "boundary_policy", "multiple_purchases": "once"}
        elif pair == ("sql.cte.order_line_reconciliation", 1):
            edge_proofs = {"missing_relationships": "unmatched_behavior", "duplicates": "line_bag", "year_boundary": "year"}
        elif pair == ("sql.windows.media_previous_play", 1):
            edge_proofs = {"ties": "tie_policy", "out_of_order_timestamps": "running_order", "single_row_groups": "null_ordering"}
        elif pair == ("sql.aggregation.support_sla_breaches", 1):
            edge_proofs = {"ticket_unresolved": "null_handling", "sla_deadline_boundary": "boundary_policy", "ticket_year_boundary": "year"}
        elif pair == ("sql.dedup.education_grade_revisions", 2):
            edge_proofs = {"canceled_latest_revision": "canceled_policy", "grade_timestamp_tie": "timestamp_tie_policy",
                           "grade_only_canceled_group": "no_valid_policy"}
        elif pair == ("sql.aggregation.warehouse_throughput", 2):
            edge_proofs = {"empty_result": "min_total_units", "zero_values": "zero_negative"}
        elif pair == ("sql.cte.inventory_net_flow", 2):
            edge_proofs = {"zero_values": "empty_group_behavior", "negative_values": "signed_units",
                           "duplicates": "count_semantics", "window_end_boundary": "window_end"}
        for edge in template.edge_cases:
            rules.append(PublicBehavior(rule_id=f"edge:{edge}", origin="instruction", kind="semantic",
                                        declaration_json=_encode(edge), source_clause=f"edge_cases:{edge}",
                                        proof_key=edge_proofs[edge]))
    for table in template.schema_definition:
        for column in table.columns:
            if (task.template_id, task.template_version) in PROFILE_IDS:
                rules.append(PublicBehavior(
                    rule_id=f"schema:raw:{table.name}.{column.name}", origin="schema", kind="input_domain",
                    declaration_json=_encode({"raw_type": column.type, "nullable": column.nullable}),
                    proof_key=raw_key(task.template_id, table.name, column.name),
                    source_clause=f"tables.{table.name}.{column.name}:pre-coercion",
                ))
            if (task.template_id, task.template_version) == ("sql.dedup.lowest_quote", 1):
                proof = "price_type" if column.name == "price_cents" else f"{column.name}_type"
                rules.append(PublicBehavior(
                    rule_id=f"schema:raw:{table.name}.{column.name}", origin="schema", kind="input_domain",
                    declaration_json=_encode({"raw_type": "int_or_none" if column.name == "price_cents" else "str"}),
                    proof_key=proof, source_clause=f"tables.{table.name}.{column.name}:pre-coercion",
                ))
            rules.append(PublicBehavior(
                rule_id=f"schema:{table.name}.{column.name}", origin="schema", kind="input_domain",
                declaration_json=_encode(column.model_dump(mode="json")),
                proof_key="schema", source_clause=f"tables.{table.name}.{column.name}",
            ))
    digest = hashlib.sha256(_encode({
        **identity, "map_version": BEHAVIOR_MAP_VERSION,
        "rules": [r.model_dump(mode="json") for r in rules],
    }).encode()).hexdigest()
    table_names = [table.name for table in task.schema_]
    if len(table_names) != len(set(table_names)):
        return PublicBehaviorMap(
            **identity, rules=tuple(rules), declaration_sha256=digest,
            blocked_reason="duplicate task schema table declarations",
        )
    # Row counts describe generated fixtures, not the SQL's public input domain.
    public_schema = {t.name: [c.model_dump() for c in t.columns] for t in template.schema_definition}
    actual_schema = {t.name: [c.model_dump() for c in t.columns] for t in task.schema_}
    _, ensured_edges = generate_fixture_tables(template, task.seed)
    expected_edges = sorted(ensured_edges)
    expected_instruction = render_instruction(template.instruction_template, build_instruction_context(
        tables={name: [] for name in public_schema},
        requirements=template.requirements, edge_cases=expected_edges,
    ))
    matches = (
        _encode(task.requirements) == _encode(template.requirements)
        and actual_schema == public_schema
        and task.family == template.family
        and task.oracle_spec == template.oracle_spec
        and task.instruction == expected_instruction
        and task.edge_cases == expected_edges
    )
    return PublicBehaviorMap(
        **identity, rules=tuple(rules), declaration_sha256=digest,
        task_matches_public_contract=matches,
        granular=granular,
        blocked_reason="" if matches else "task differs from public declarations",
    )
