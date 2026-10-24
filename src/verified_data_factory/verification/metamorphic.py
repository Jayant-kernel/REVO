"""Metamorphic relations (Phase 4).

Each relation transforms the fixture, re-executes the SAME candidate, and
checks a known A-vs-B relation — no oracle involved at this stage (oracle
comparison is a separate pipeline stage). Relations are family-justified:

- ROW_PERMUTATION (all): shuffled inputs, same semantic result.
- ADD_IRRELEVANT_CUSTOMER (join/cte/subquery/window families): an entity
  with no orders contributes no rows under INNER-JOIN exclusion.
- ADD_DUPLICATE_EVENT (dedup/funnel/retention): duplicates cannot move
  latest-wins / first-occurrence / any-qualifying outcomes.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.task_engine.models import TaskInstance

from . import comparator as compare_mod
from .backend import ExecutionBackend
from .errors import BackendError, OracleError
from .models import ComparisonPolicy, ExpectedResult, MetamorphicOutcome, MetamorphicResult


class MetamorphicContext:
    """Inputs for one relation check (candidate result A + transform)."""

    __slots__ = (
        "backend",
        "candidate",
        "candidate_columns",
        "candidate_rows",
        "candidate_types",
        "order",
        "policy",
        "seed",
        "tables",
        "task",
    )

    def __init__(
        self,
        task: TaskInstance,
        candidate: CandidateSolution,
        tables: dict[str, list[dict[str, Any]]],
        candidate_columns: list[str],
        candidate_rows: list[list[Any]],
        order: Any,
        backend: ExecutionBackend,
        policy: ComparisonPolicy,
        seed: int,
        candidate_types: list[str] | None = None,
    ) -> None:
        self.task = task
        self.candidate = candidate
        self.tables = tables
        self.candidate_columns = candidate_columns
        self.candidate_rows = candidate_rows
        self.order = order
        self.backend = backend
        self.policy = policy
        self.seed = seed
        self.candidate_types = candidate_types or []


def _compare_against_original(
    ctx: MetamorphicContext, tables: dict[str, list[dict[str, Any]]], label: str
) -> tuple[bool, str]:
    execution = ctx.backend.run(ctx.task, ctx.candidate, tables, label)
    if execution.status != "SUCCEEDED" or execution.result_data is None:
        return False, f"metamorphic execution {execution.status}"
    expected = ExpectedResult(
        columns=ctx.candidate_columns, rows=ctx.candidate_rows, order=ctx.order,
        column_types=ctx.candidate_types,
    )
    comparison = compare_mod.compare(
        expected,
        [c.name for c in execution.result_data.columns],
        execution.result_data.rows,
        ctx.policy,
        column_types=[c.type for c in execution.result_data.columns],
    )
    if comparison.match:
        return True, ""
    return False, f"expected {comparison.expected_rows} rows, got {comparison.actual_rows}"


def relate_row_permutation(ctx: MetamorphicContext) -> MetamorphicOutcome:
    rng = random.Random(ctx.seed)
    shuffled = {name: list(rows) for name, rows in ctx.tables.items()}
    for rows in shuffled.values():
        rng.shuffle(rows)
    passed, detail = _compare_against_original(ctx, shuffled, "metamorphic:row_permutation")
    return MetamorphicOutcome(
        relation_id="ROW_PERMUTATION", applicable=True, passed=passed, detail=detail
    )


def relate_add_irrelevant_customer(ctx: MetamorphicContext) -> MetamorphicOutcome:
    customers = ctx.tables.get("customers")
    if not customers:
        return MetamorphicOutcome(
            relation_id="ADD_IRRELEVANT_CUSTOMER",
            applicable=False,
            passed=False,
            detail="no customers table",
        )
    ghost_id = max(c["customer_id"] for c in customers) + 1
    ghost = {
        "customer_id": ghost_id,
        "name": "Meta Ghost",
        "country": "XX",
        "signup_date": "2024-06-01",
    }
    tables = {**ctx.tables, "customers": [*customers, ghost]}
    passed, detail = _compare_against_original(ctx, tables, "metamorphic:add_irrelevant_customer")
    return MetamorphicOutcome(
        relation_id="ADD_IRRELEVANT_CUSTOMER", applicable=True, passed=passed, detail=detail
    )


def relate_add_irrelevant_account(ctx: MetamorphicContext) -> MetamorphicOutcome:
    accounts = ctx.tables.get("accounts")
    if not accounts:
        return MetamorphicOutcome(
            relation_id="ADD_IRRELEVANT_ACCOUNT",
            applicable=False,
            passed=False,
            detail="no accounts table",
        )
    ghost = {
        "account_id": max(a["account_id"] for a in accounts) + 1,
        "account_name": "Unused workspace",
        "account_status": "active",
    }
    tables = {**ctx.tables, "accounts": [*accounts, ghost]}
    passed, detail = _compare_against_original(ctx, tables, "metamorphic:add_irrelevant_account")
    return MetamorphicOutcome(
        relation_id="ADD_IRRELEVANT_ACCOUNT", applicable=True, passed=passed, detail=detail
    )


def relate_add_duplicate_event(ctx: MetamorphicContext) -> MetamorphicOutcome:
    rows = ctx.tables.get("events", [])
    if not rows:
        return MetamorphicOutcome(
            relation_id="ADD_DUPLICATE_EVENT",
            applicable=False,
            passed=False,
            detail="no events table",
        )
    dup = dict(rows[0])
    dup["event_id"] = max(r["event_id"] for r in rows if isinstance(r.get("event_id"), int)) + 1
    tables = {**ctx.tables, "events": [*rows, dup]}
    passed, detail = _compare_against_original(ctx, tables, "metamorphic:add_duplicate_event")
    return MetamorphicOutcome(
        relation_id="ADD_DUPLICATE_EVENT", applicable=True, passed=passed, detail=detail
    )


def contract_relation_tables(task: TaskInstance, tables: dict[str, list[dict[str, Any]]], relation: str) -> tuple[dict[str, list[dict[str, Any]]] | None, str]:
    """Explicit qualified-contract transforms, not table-name fallbacks."""
    result = deepcopy(tables)
    pair = task.template_id, task.template_version
    if pair == ("sql.cte.inventory_net_flow", 2):
        if relation not in {"INVENTORY_RECEIPT_REPEAT", "INVENTORY_UNPOSTED_ISSUE"}:
            return None, "NOT_APPLICABLE: unknown inventory row-bag relation"
        selected = next((row for row in result["receipts"] if row["status"] == "posted"
                         and str(row["occurred_on"])[:4] == "2025" and row["units"] != 0), None)
        if selected is None:
            return None, "precondition: nonzero posted current-year receipt required"
        if relation == "INVENTORY_RECEIPT_REPEAT":
            result["receipts"].append(dict(selected))
        else:
            result["issues"].append({**selected, "status": "failed"})
        return result, "receipt input row repeated once or same-warehouse unposted issue appended"
    if pair == ("sql.subqueries.education_all_required", 1):
        if relation not in {"REQUIRED_COURSE_DUPLICATE", "REQUIRED_FAILED_ATTEMPT"}:
            return None, "NOT_APPLICABLE: unknown required-course relation"
        programs = {row["program_id"] for row in result["students"]}
        requirement = next((row for row in result["required_courses"] if row["program_id"] in programs), None)
        if requirement is None:
            return None, "precondition: a student's program must have a required course"
        if relation == "REQUIRED_COURSE_DUPLICATE":
            result["required_courses"].append(dict(requirement))
        else:
            passing = next((row for row in result["attempts"] if row["score"] is not None
                and row["score"] >= task.requirements["passing_score"]
                and any(student["student_id"] == row["student_id"]
                    and any(req["program_id"] == student["program_id"] and req["course_id"] == row["course_id"]
                            for req in result["required_courses"]) for student in result["students"])), None)
            if passing is None:
                return None, "precondition: passing attempt for an enrolled required course needed"
            identifier = max(row["attempt_id"] for row in result["attempts"])+1
            if identifier > 2**31-1:
                return None, "precondition: spare INTEGER attempt identifier required"
            result["attempts"].append({**passing, "attempt_id": identifier, "score": 49})
        return result, "distinct requirement repeated or failed attempt appended; an existing pass is not erased"
    if pair == ("sql.aggregation.warehouse_throughput", 2):
        if relation not in {"THROUGHPUT_POSTED_DUPLICATE", "THROUGHPUT_FAILED_ROW"}:
            return None, "NOT_APPLICABLE: unknown throughput relation"
        selected_load = next((row for row in result["warehouse_loads"] if row["status"] == "posted"
                              and str(row["loaded_on"])[:4] == "2025"), None)
        if selected_load is None:
            return None, "precondition: posted current-year load required"
        extra_load = dict(selected_load)
        if relation == "THROUGHPUT_FAILED_ROW":
            extra_load["status"] = "failed"
        result["warehouse_loads"].append(extra_load)
        return result, "exact input-row bag contribution duplicated or identical nonposted load appended"
    from .qualification.delivery_profiles import get_profile

    followup = get_profile(*pair)
    if followup is not None:
        transformed: tuple[dict[str, list[dict[str, Any]]] | None, str] = followup.transform(tables, relation)
        return transformed
    if pair == ("sql.dedup.lowest_quote", 1):
        if relation not in {"QUOTE_WINNER_REPEAT", "QUOTE_UNKNOWN"}:
            return None, "NOT_APPLICABLE: unknown lowest-quote relation"
        from .qualification.lowest_quote_profile import expected

        winners = expected(task.requirements, result).rows
        if not winners:
            return None, "precondition: known quote winner required"
        part, supplier, price = winners[0]
        result["quotes"].append({"part": part, "supplier": supplier,
                                 "price_cents": price if relation == "QUOTE_WINNER_REPEAT" else None})
        return result, "winning triple repeated or unknown quote appended; selected winner unchanged"
    if pair == ("sql.dedup.education_grade_revisions", 2):
        if relation not in {"GRADE_VALID_REPEAT", "GRADE_CANCELLED_LATEST"}:
            return None, "NOT_APPLICABLE: unknown immutable-grade relation"
        valid_revisions = [row for row in result["grade_revisions"] if row["revision_status"] == "valid"]
        if not valid_revisions:
            return None, "precondition: at least one valid grade revision required"
        winner = max(valid_revisions, key=lambda row: (datetime.fromisoformat(str(row["recorded_at"])), row["revision_id"]))
        added_revision = dict(winner)
        if relation == "GRADE_CANCELLED_LATEST":
            same_pair = [row for row in result["grade_revisions"] if (row["student_id"],row["course_id"]) == (winner["student_id"],winner["course_id"])]
            at = max(datetime.fromisoformat(str(row["recorded_at"])) for row in same_pair)
            try:
                added_revision["recorded_at"] = (at+timedelta(seconds=1)).isoformat(sep=" ")
            except OverflowError:
                return None, "precondition: spare timestamp after latest pair revision required"
            added_revision.update(revision_status="cancelled", grade="cancelled-added")
        result["grade_revisions"].append(added_revision)
        return result, "immutable valid winner repeated, or a later cancelled revision appended without affecting selection"
    if pair == ("sql.aggregation.support_sla_breaches", 1):
        if relation not in {"SUPPORT_BREACH_DUPLICATE", "SUPPORT_ON_TIME_ROW"}:
            return None, "NOT_APPLICABLE: unknown support-breach relation"
        selected_ticket = next((row for row in result["support_tickets"] if row["resolved_at"] is not None
            and str(row["opened_at"])[:4] == "2025"
            and datetime.fromisoformat(str(row["resolved_at"])) > datetime.fromisoformat(str(row["due_at"]))), None)
        if selected_ticket is None:
            return None, "precondition: current-year opened resolved breach required"
        extra_ticket = dict(selected_ticket)
        if relation == "SUPPORT_ON_TIME_ROW":
            extra_ticket["resolved_at"] = extra_ticket["due_at"]
        result["support_tickets"].append(extra_ticket)
        return result, "exact breached ticket row duplicate, or resolution changed to equal declared deadline"
    if pair == ("sql.windows.media_previous_play", 1):
        if relation not in {"PREVIOUS_PLAY_PARTIAL", "PREVIOUS_PLAY_OTHER_VIEWER"}:
            return None, "NOT_APPLICABLE: unknown previous-play relation"
        selected = next((row for row in result["plays"] if row["status"] == "completed"
                         and str(row["played_at"])[:4] == "2025"), None)
        if selected is None:
            return None, "precondition: completed current-year playback required"
        identifier = max(row["play_id"] for row in result["plays"]) + 1
        viewer = max(row["viewer_id"] for row in result["plays"]) + 1
        if max(identifier, viewer) > 2**31 - 1:
            return None, "precondition: spare INTEGER playback/viewer identifiers required"
        extra = {**selected, "play_id": identifier}
        if relation == "PREVIOUS_PLAY_PARTIAL":
            extra["status"] = "partial"
        else:
            extra["viewer_id"] = viewer
        result["plays"].append(extra)
        return result, "fresh playback; partial excluded or independent viewer history starts with NULL"
    if pair == ("sql.cte.order_line_reconciliation", 1):
        if relation not in {"RECONCILIATION_HEADER_DUPLICATE", "RECONCILIATION_LINE_DUPLICATE"}:
            return None, "NOT_APPLICABLE: unknown reconciliation relation"
        selected = next((row for row in result["orders"] if row["order_status"] == "completed"
                         and str(row["ordered_on"])[:4] == "2025"), None)
        if selected is None:
            return None, "precondition: completed current-year order required"
        if relation == "RECONCILIATION_HEADER_DUPLICATE":
            result["orders"].append(dict(selected))
        else:
            selected_line = next((row for row in result["order_lines"] if row["order_id"] == selected["order_id"]), None)
            if selected_line is None:
                return None, "precondition: matching line required"
            result["order_lines"].append(dict(selected_line))
        return result, "exact header or matching line row duplicated, declared multiplicity retained"
    if pair == ("sql.retention.saas_repeat_payment", 1):
        if relation not in {"REPEAT_PAYMENT_DUPLICATE", "REPEAT_PAYMENT_PRIOR_COHORT"}:
            return None, "NOT_APPLICABLE: unknown repeat-payment relation"
        paid = [row for row in result["billing"] if row["status"] == "paid" and row["paid_on"] is not None]
        if not paid:
            return None, "precondition: paid history required"
        extra = dict(paid[-1])
        if relation == "REPEAT_PAYMENT_PRIOR_COHORT":
            from datetime import date

            selected = next((row for row in paid if min(date.fromisoformat(str(other["paid_on"]))
                for other in paid if other["account_id"] == row["account_id"]).year == 2025), None)
            if selected is None:
                return None, "precondition: account in current-year first-paid cohort required"
            extra = dict(selected)
            extra["paid_on"] = "2024-12-31"
        result["billing"].append(extra)
        return result, "duplicate paid invoice is set-invariant; prior first payment removes its account from cohort"
    if pair == ("sql.temporal.clinic_weekly_visits", 1):
        if relation not in {"WEEKLY_VISIT_DUPLICATE", "WEEKLY_VISIT_CANCELLED"}:
            return None, "NOT_APPLICABLE: unknown weekly-visits relation"
        selected = next((row for row in result["visits"] if row["status"] == "completed"
                         and row["started_at"] is not None and str(row["started_at"])[:4] == "2025"), None)
        if selected is None:
            return None, "precondition: completed current-year visit required"
        result["visits"].append({**selected, "status": "cancelled" if relation == "WEEKLY_VISIT_CANCELLED" else "completed"})
        return result, "same clinic/week; duplicate row counts once more, cancelled row excluded"
    if pair == ("sql.joins.logistics_final_leg", 1):
        if relation not in {"FINAL_LEG_DUPLICATE", "FINAL_LEG_UNDELIVERED"}:
            return None, "NOT_APPLICABLE: unknown final-leg relation"
        eligible = [row for row in result["shipments"] if row["delivered_on"] is not None
                    and str(row["delivered_on"])[:4] == "2025"
                    and any(leg["leg_id"] == row["final_leg_id"]
                            and any(carrier["carrier_id"] == leg["carrier_id"] for carrier in result["carriers"])
                            for leg in result["legs"])]
        if not eligible:
            return None, "precondition: delivered shipment with complete declared leg/carrier required"
        if relation == "FINAL_LEG_DUPLICATE":
            result["legs"].append(dict(next(leg for leg in result["legs"]
                if leg["leg_id"] == eligible[0]["final_leg_id"]
                and any(carrier["carrier_id"] == leg["carrier_id"] for carrier in result["carriers"]))))
        else:
            result["shipments"].append({**eligible[0], "delivered_on": None})
        return result, "declared key/row bag retained; matching leg duplicate or undelivered shipment appended"
    if pair == ("sql.joins.saas_paid_invoices", 1):
        if relation not in {"PAID_INVOICE_DUPLICATE", "PAID_INACTIVE_ACCOUNT"}:
            return None, "NOT_APPLICABLE: unknown paid-invoice relation"
        active = {row["account_id"] for row in result["accounts"] if row["account_status"] == "active"}
        eligible = [row for row in result["invoices"] if row["account_id"] in active
                    and row["invoice_status"] == "paid" and str(row["issued_on"])[:4] == "2025"]
        if not eligible:
            return None, "precondition: matching paid active-account invoice required"
        extra = dict(eligible[0])
        if relation == "PAID_INACTIVE_ACCOUNT":
            identifier = max(row["account_id"] for row in result["accounts"]) + 1
            if identifier in {row["account_id"] for row in result["invoices"]} or identifier > 2**31 - 1:
                return None, "precondition: spare nonreferenced INTEGER account identifier required"
            result["accounts"].append({"account_id": identifier, "account_name": "inactive-added", "account_status": "suspended"})
            extra["account_id"] = identifier
            extra["invoice_id"] = max(row["invoice_id"] for row in result["invoices"]) + 1
            if extra["invoice_id"] > 2**31 - 1:
                return None, "precondition: spare INTEGER invoice identifier required"
        result["invoices"].append(extra)
        return result, "declared bag preserved; duplicate invoice or fresh suspended-account invoice appended"
    if pair == ("sql.subqueries.exists", 2):
        if relation not in {"EXISTS_QUALIFYING_ORDER_DUPLICATE", "EXISTS_CUSTOMER_ROW_DUPLICATE"}:
            return None, "NOT_APPLICABLE: unknown EXISTS relation"
        eligible = [row for row in result["orders"] if row["status"] == "completed"
                    and str(row["order_date"])[:4] == "2025" and row["amount"] > 500]
        selected_customer = next((customer for customer in result["customers"]
                         if any(row["customer_id"] == customer["customer_id"] for row in eligible)), None)
        if selected_customer is None:
            return None, "precondition: customer with a qualifying order required"
        if relation == "EXISTS_CUSTOMER_ROW_DUPLICATE":
            result["customers"].append(dict(selected_customer))
        else:
            result["orders"].append(dict(next(row for row in eligible if row["customer_id"] == selected_customer["customer_id"])))
        return result, "customer-row bag preserved; duplicate qualifying order or qualifying customer row appended"
    if (task.template_id, task.template_version) == ("sql.aggregation.fulfillment_sla_dashboard", 1):
        if relation not in {"SLA_DELIVERED_CLONE", "SLA_CANCELLED_ROW"}:
            return None, "NOT_APPLICABLE: unknown SLA relation"
        rows = result["fulfillments"]
        eligible = [row for row in rows if row["fulfillment_status"] == "delivered"
                    and row["delivered_at"] is not None and str(row["shipped_at"]).startswith("2025")]
        if not eligible:
            return None, "precondition: an eligible fulfillment is required"
        identifier = max(row["fulfillment_id"] for row in rows) + 1
        if identifier > 2**31 - 1:
            return None, "precondition: spare INTEGER-domain identifier required"
        extra = {**eligible[0], "fulfillment_id": identifier}
        if relation == "SLA_CANCELLED_ROW":
            extra["fulfillment_status"] = "cancelled"
        rows.append(extra)
        return result, "fresh fulfillment identifier; warehouse/year/deadline preserved; declared status changed only for cancellation"
    if relation not in {"SAAS_LATER_PAYMENT", "SAAS_INCOMPLETE_ENTITY", "SAAS_EXCLUDED_GROUP", "SCRAP_ADDITIVITY", "SCRAP_EXCLUDED_ROW"}:
        return None, "NOT_APPLICABLE: unknown contract relation"
    if task.template_id == "sql.funnel.saas_activation_payment" and task.template_version == 2:
        rows = result["account_funnel"]
        scoped = [r for r in rows if str(r["occurred_at"])[:4] == str(task.requirements["year"]) and r["status"] in task.requirements["funnel_steps"]]
        if not scoped:
            return None, "precondition: an in-scope group is required"
        record_id = max(r["record_id"] for r in rows) + 1
        entity_id = max(r["entity_id"] for r in rows) + 1
        group = scoped[0]["group_key"]
        if relation == "SAAS_LATER_PAYMENT":
            by_entity: dict[int, list[dict[str, Any]]] = {}
            for row in scoped:
                by_entity.setdefault(row["entity_id"], []).append(row)
            selected_chain = None
            for members in by_entity.values():
                progress = 0
                for row in sorted(members, key=lambda r: (datetime.fromisoformat(str(r["occurred_at"])), r["sequence"])):
                    if progress < 4 and row["status"] == task.requirements["funnel_steps"][progress]:
                        progress += 1
                if progress == 4:
                    selected_chain = members
                    break
            if selected_chain is None:
                return None, "precondition: an already-completed entity is required"
            last = max(selected_chain, key=lambda r: (datetime.fromisoformat(str(r["occurred_at"])), r["sequence"]))
            extra = {**last, "record_id": record_id, "sequence": max(r["sequence"] for r in rows if r["entity_id"] == last["entity_id"]) + 1,
                     "status": "payment", "amount": 1}
        else:
            if relation == "SAAS_EXCLUDED_GROUP":
                group = f"excluded-{entity_id}"
                while group in {r["group_key"] for r in rows}:
                    group += "-new"
            extra = {"record_id": record_id, "entity_id": entity_id, "group_key": group,
                     "occurred_at": f"{task.requirements['year']}-06-15 12:00:00", "sequence": 1,
                     "status": "cancelled" if relation == "SAAS_EXCLUDED_GROUP" else "signup", "amount": 11}
        if max(extra["record_id"], extra["entity_id"], extra["sequence"]) > 2**31 - 1:
            return None, "precondition: spare INTEGER-domain identifiers/order key required"
        rows.append(extra)
        return result, "unique order key, one group/entity, scope and original matched chain preserved"
    if task.template_id == "sql.aggregation.manufacturing_line_scrap" and task.template_version == 1:
        rows = result["production_runs"]
        eligible = [r for r in rows if r["status"] == "eligible" and str(r["occurred_at"])[:4] == str(task.requirements["year"])]
        if not eligible:
            return None, "precondition: an existing eligible line required"
        extra = {**eligible[0], "record_id": max(r["record_id"] for r in rows) + 1,
                 "entity_id": max(r["entity_id"] for r in rows) + 1,
                 "amount": 11, "status": "eligible" if relation == "SCRAP_ADDITIVITY" else "ineligible"}
        rows.append(extra)
        return result, "fresh identifiers, existing line, fixed year and explicit eligibility preserved"
    return None, "BLOCKED: contract-specific rule profile is not qualified"


def _contract_relation(ctx: MetamorphicContext, relation: str) -> MetamorphicOutcome:
    tables, precondition = contract_relation_tables(ctx.task, ctx.tables, relation)
    if tables is None:
        return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=False, passed=False, detail=precondition)
    reference = ctx
    if relation == "INVENTORY_RECEIPT_REPEAT":
        if set(ctx.candidate_columns) != {"warehouse", "net_units"}:
            return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=True,
                                      passed=False, detail="required inventory output schema absent")
        added = tables["receipts"][-1]
        w, n = (ctx.candidate_columns.index(name) for name in ("warehouse", "net_units"))
        expected_rows = deepcopy(ctx.candidate_rows)
        group = next((row for row in expected_rows if row[w] == added["warehouse"]), None)
        if group is None:
            return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=True,
                                      passed=False, detail="qualifying receipt warehouse absent from output")
        group[n] = int(group[n])+added["units"]
        reference = MetamorphicContext(ctx.task, ctx.candidate, ctx.tables, ctx.candidate_columns, expected_rows,
                                      ctx.order, ctx.backend, ctx.policy, ctx.seed, candidate_types=ctx.candidate_types)
    if relation == "THROUGHPUT_POSTED_DUPLICATE":
        if set(ctx.candidate_columns) != {"warehouse", "total_units"}:
            return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=True,
                                      passed=False, detail="required throughput output schema absent")
        extra_load = tables["warehouse_loads"][-1]
        warehouse = extra_load["warehouse"]
        total = sum(row["units"] for row in tables["warehouse_loads"] if row["warehouse"] == warehouse
                    and row["status"] == "posted" and str(row["loaded_on"])[:4] == "2025")
        w = ctx.candidate_columns.index("warehouse")
        expected_rows = [row for row in deepcopy(ctx.candidate_rows) if row[w] != warehouse]
        if total >= int(ctx.task.requirements["min_total_units"]):
            values = {"warehouse": warehouse, "total_units": total}
            expected_rows.append([values[column] for column in ctx.candidate_columns])
        expected_rows.sort(key=lambda row:row[w])
        reference = MetamorphicContext(ctx.task, ctx.candidate, ctx.tables, ctx.candidate_columns, expected_rows,
                                      ctx.order, ctx.backend, ctx.policy, ctx.seed, candidate_types=ctx.candidate_types)
    if relation == "SUPPORT_BREACH_DUPLICATE":
        if set(ctx.candidate_columns) != {"team", "priority", "breach_count"}:
            return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=True,
                                      passed=False, detail="required support breach output schema absent")
        extra_ticket = tables["support_tickets"][-1]
        t, p, n = (ctx.candidate_columns.index(column) for column in ("team", "priority", "breach_count"))
        expected_rows = deepcopy(ctx.candidate_rows)
        selected_group = next((row for row in expected_rows if row[t] == extra_ticket["team"]
                               and row[p] == extra_ticket["priority"]), None)
        if selected_group is None:
            return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=True,
                                      passed=False, detail="eligible breach group missing from candidate output")
        selected_group[n] = int(selected_group[n])+1
        reference = MetamorphicContext(ctx.task, ctx.candidate, ctx.tables, ctx.candidate_columns, expected_rows,
                                      ctx.order, ctx.backend, ctx.policy, ctx.seed, candidate_types=ctx.candidate_types)
    if relation == "PREVIOUS_PLAY_OTHER_VIEWER":
        if set(ctx.candidate_columns) != {"play_id", "previous_play_id"}:
            return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=True,
                                      passed=False, detail="required playback output schema absent")
        values = {"play_id": tables["plays"][-1]["play_id"], "previous_play_id": None}
        expected_rows = [*deepcopy(ctx.candidate_rows), [values[column] for column in ctx.candidate_columns]]
        expected_rows.sort(key=lambda row: row[ctx.candidate_columns.index("play_id")])
        reference = MetamorphicContext(ctx.task, ctx.candidate, ctx.tables, ctx.candidate_columns, expected_rows,
                                      ctx.order, ctx.backend, ctx.policy, ctx.seed, candidate_types=ctx.candidate_types)
    if relation in {"RECONCILIATION_HEADER_DUPLICATE", "RECONCILIATION_LINE_DUPLICATE"}:
        # Recompute only the changed order's analytical delta, independently of the oracle.
        if set(ctx.candidate_columns) != {"order_id", "header_total_cents", "line_total_cents"}:
            return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=True,
                                      passed=False, detail="required reconciliation output schema absent")
        owner = tables["orders"][-1]["order_id"] if relation == "RECONCILIATION_HEADER_DUPLICATE" else tables["order_lines"][-1]["order_id"]
        total = sum(row["quantity"]*row["unit_price_cents"] for row in tables["order_lines"] if row["order_id"] == owner)
        key = ctx.candidate_columns.index("order_id")
        expected_rows = [row for row in ctx.candidate_rows if row[key] != owner]
        for header in tables["orders"]:
            if header["order_id"] == owner and header["order_status"] == "completed" and str(header["ordered_on"])[:4] == "2025" and header["header_total_cents"] != total:
                values = {"order_id": owner, "header_total_cents": header["header_total_cents"], "line_total_cents": total}
                expected_rows.append([values[column] for column in ctx.candidate_columns])
        expected_rows.sort(key=lambda row: row[key])
        reference = MetamorphicContext(ctx.task, ctx.candidate, ctx.tables, ctx.candidate_columns, expected_rows,
                                      ctx.order, ctx.backend, ctx.policy, ctx.seed, candidate_types=ctx.candidate_types)
    if relation == "REPEAT_PAYMENT_PRIOR_COHORT":
        if ctx.candidate_columns != ["account_id"]:
            return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=True,
                                      passed=False, detail="required retention output schema absent")
        excluded = tables["billing"][-1]["account_id"]
        expected_rows = [row for row in ctx.candidate_rows if row[0] != excluded]
        reference = MetamorphicContext(ctx.task, ctx.candidate, ctx.tables, ctx.candidate_columns, expected_rows,
                                      ctx.order, ctx.backend, ctx.policy, ctx.seed, candidate_types=ctx.candidate_types)
    if relation == "WEEKLY_VISIT_DUPLICATE":
        from datetime import datetime, timedelta

        if set(ctx.candidate_columns) != {"clinic", "week_start", "visit_count"}:
            return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=True,
                                      passed=False, detail="required weekly output schema absent")
        extra = tables["visits"][-1]
        at = datetime.fromisoformat(str(extra["started_at"]))
        week = (at.date() - timedelta(days=at.weekday())).isoformat()
        c, w, n = (ctx.candidate_columns.index(column) for column in ("clinic", "week_start", "visit_count"))
        expected_rows = deepcopy(ctx.candidate_rows)
        matched = False
        for row in expected_rows:
            if row[c] == extra["clinic"] and str(row[w]) == week:
                row[n] = int(row[n]) + 1
                matched = True
        if not matched:
            return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=True,
                                      passed=False, detail="eligible weekly group missing from candidate output")
        reference = MetamorphicContext(ctx.task, ctx.candidate, ctx.tables, ctx.candidate_columns, expected_rows,
                                      ctx.order, ctx.backend, ctx.policy, ctx.seed, candidate_types=ctx.candidate_types)
    if relation in {"PAID_INVOICE_DUPLICATE", "EXISTS_CUSTOMER_ROW_DUPLICATE", "FINAL_LEG_DUPLICATE"}:
        # Extend the original result bag by the exact appended input-row image.
        expected_rows = deepcopy(ctx.candidate_rows)
        if relation == "PAID_INVOICE_DUPLICATE":
            extra = tables["invoices"][-1]
            additions = [{"invoice_id": extra["invoice_id"], "account_name": account["account_name"],
                          "amount_cents": extra["amount_cents"]}
                         for account in tables["accounts"] if account["account_id"] == extra["account_id"]
                         and account["account_status"] == "active"]
            order_column = "invoice_id"
        elif relation == "FINAL_LEG_DUPLICATE":
            extra = tables["legs"][-1]
            additions = [{"shipment_id": shipment["shipment_id"], "depot": extra["depot"],
                          "carrier_name": carrier["carrier_name"]}
                         for shipment in tables["shipments"]
                         if shipment["final_leg_id"] == extra["leg_id"]
                         and shipment["delivered_on"] is not None and str(shipment["delivered_on"])[:4] == "2025"
                         for carrier in tables["carriers"] if carrier["carrier_id"] == extra["carrier_id"]]
            order_column = "shipment_id"
        else:
            extra = tables["customers"][-1]
            additions = [{"customer_id": extra["customer_id"], "name": extra["name"]}]
            order_column = "customer_id"
        if any(set(row) != set(ctx.candidate_columns) for row in additions):
            return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=True,
                                      passed=False, detail="required bag output schema absent")
        expected_rows.extend([[row[column] for column in ctx.candidate_columns] for row in additions])
        expected_rows.sort(key=lambda row: row[ctx.candidate_columns.index(order_column)])
        reference = MetamorphicContext(ctx.task, ctx.candidate, ctx.tables, ctx.candidate_columns, expected_rows,
                                      ctx.order, ctx.backend, ctx.policy, ctx.seed, candidate_types=ctx.candidate_types)
    if relation == "SCRAP_ADDITIVITY":
        if "group_key" not in ctx.candidate_columns or "total_amount" not in ctx.candidate_columns:
            return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=True, passed=False, detail="required additive output schema absent")
        group = tables["production_runs"][-1]["group_key"]
        g, a = ctx.candidate_columns.index("group_key"), ctx.candidate_columns.index("total_amount")
        expected_rows = deepcopy(ctx.candidate_rows)
        found = False
        for row in expected_rows:
            if row[g] == group:
                row[a] = int(row[a]) + 11
                found = True
        if not found:
            return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=True, passed=False, detail="eligible line absent from candidate output")
        reference = MetamorphicContext(ctx.task, ctx.candidate, ctx.tables, ctx.candidate_columns, expected_rows,
                                        ctx.order, ctx.backend, ctx.policy, ctx.seed, candidate_types=ctx.candidate_types)
    passed, detail = _compare_against_original(reference, tables, "metamorphic:" + relation.lower())
    return MetamorphicOutcome(relation_id=relation, relation_version=2, applicable=True, passed=passed,
                              detail=detail if not passed else precondition)


def relate_saas_later_payment(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "SAAS_LATER_PAYMENT")


def relate_saas_incomplete_entity(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "SAAS_INCOMPLETE_ENTITY")


def relate_saas_excluded_group(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "SAAS_EXCLUDED_GROUP")


def relate_scrap_additivity(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "SCRAP_ADDITIVITY")


def relate_scrap_excluded_row(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "SCRAP_EXCLUDED_ROW")


def relate_paid_invoice_duplicate(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "PAID_INVOICE_DUPLICATE")


def relate_paid_inactive_account(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "PAID_INACTIVE_ACCOUNT")


def relate_exists_order_duplicate(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "EXISTS_QUALIFYING_ORDER_DUPLICATE")


def relate_exists_customer_duplicate(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "EXISTS_CUSTOMER_ROW_DUPLICATE")


def relate_final_leg_duplicate(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "FINAL_LEG_DUPLICATE")


def relate_final_leg_undelivered(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "FINAL_LEG_UNDELIVERED")


def relate_weekly_visit_duplicate(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "WEEKLY_VISIT_DUPLICATE")


def relate_weekly_visit_cancelled(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "WEEKLY_VISIT_CANCELLED")


def relate_repeat_payment_duplicate(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "REPEAT_PAYMENT_DUPLICATE")


def relate_repeat_payment_prior_cohort(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "REPEAT_PAYMENT_PRIOR_COHORT")


def relate_reconciliation_header_duplicate(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "RECONCILIATION_HEADER_DUPLICATE")


def relate_reconciliation_line_duplicate(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "RECONCILIATION_LINE_DUPLICATE")


def relate_previous_play_partial(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "PREVIOUS_PLAY_PARTIAL")


def relate_previous_play_other_viewer(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "PREVIOUS_PLAY_OTHER_VIEWER")


def relate_support_breach_duplicate(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "SUPPORT_BREACH_DUPLICATE")


def relate_support_on_time_row(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "SUPPORT_ON_TIME_ROW")


def relate_grade_valid_repeat(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "GRADE_VALID_REPEAT")


def relate_grade_cancelled_latest(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "GRADE_CANCELLED_LATEST")


def relate_throughput_posted_duplicate(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "THROUGHPUT_POSTED_DUPLICATE")


def relate_throughput_failed_row(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "THROUGHPUT_FAILED_ROW")


def relate_required_course_duplicate(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "REQUIRED_COURSE_DUPLICATE")


def relate_required_failed_attempt(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "REQUIRED_FAILED_ATTEMPT")


def relate_inventory_receipt_repeat(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "INVENTORY_RECEIPT_REPEAT")


def relate_inventory_unposted_issue(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "INVENTORY_UNPOSTED_ISSUE")


RelationFn = Callable[[MetamorphicContext], MetamorphicOutcome]


def relate_quote_winner_repeat(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "QUOTE_WINNER_REPEAT")


def relate_quote_unknown(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "QUOTE_UNKNOWN")


def relate_language_orphan(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "LANGUAGE_ORPHAN")


def relate_language_null_keys(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "LANGUAGE_NULL_KEYS")


def relate_pareto_incomplete(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "PARETO_INCOMPLETE_COMPETITOR")


def relate_pareto_equal_duration(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "PARETO_EQUAL_DURATION_DOMINATED")

def relate_renewal_adjacent(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "RENEWAL_ADJACENT")


def relate_renewal_orphan(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "RENEWAL_ORPHAN")


def relate_queue_reverse(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "QUEUE_REVERSE_INPUT")


def relate_queue_relabel(ctx: MetamorphicContext) -> MetamorphicOutcome:
    return _contract_relation(ctx, "QUEUE_RELABEL")


RELATION_REGISTRY: dict[str, list[RelationFn]] = {
    "simple_joins": [relate_row_permutation, relate_add_irrelevant_customer],
    "multi_joins": [relate_row_permutation, relate_add_irrelevant_customer],
    "aggregation": [relate_row_permutation],
    "cte": [relate_row_permutation, relate_add_irrelevant_customer],
    "subqueries": [relate_row_permutation, relate_add_irrelevant_customer],
    "window_functions": [relate_row_permutation, relate_add_irrelevant_customer],
    "temporal": [relate_row_permutation],
    "deduplication": [relate_row_permutation, relate_add_duplicate_event],
    "retention": [relate_row_permutation, relate_add_duplicate_event],
    "funnel": [relate_row_permutation, relate_add_duplicate_event],
}

RELATION_VERSION = 1

TEMPLATE_RELATION_OVERRIDES: dict[str | tuple[str, int], list[RelationFn]] = {
    ("sql.retention.renewal_coverage", 1): [relate_row_permutation, relate_renewal_adjacent, relate_renewal_orphan],
    ("sql.windows.queue_batches", 1): [relate_row_permutation, relate_queue_reverse, relate_queue_relabel],
    ("sql.joins.requested_language_titles", 1): [relate_row_permutation, relate_language_orphan, relate_language_null_keys],
    ("sql.subqueries.pareto_shipping", 1): [relate_row_permutation, relate_pareto_incomplete, relate_pareto_equal_duration],
    ("sql.dedup.lowest_quote", 1): [relate_row_permutation, relate_quote_winner_repeat, relate_quote_unknown],
    ("sql.cte.inventory_net_flow", 2): [relate_row_permutation, relate_inventory_receipt_repeat, relate_inventory_unposted_issue],
    ("sql.subqueries.education_all_required", 1): [relate_row_permutation, relate_required_course_duplicate, relate_required_failed_attempt],
    ("sql.aggregation.warehouse_throughput", 2): [relate_row_permutation, relate_throughput_posted_duplicate, relate_throughput_failed_row],
    ("sql.dedup.education_grade_revisions", 2): [relate_row_permutation, relate_grade_valid_repeat, relate_grade_cancelled_latest],
    ("sql.aggregation.support_sla_breaches", 1): [relate_row_permutation, relate_support_breach_duplicate, relate_support_on_time_row],
    ("sql.windows.media_previous_play", 1): [relate_row_permutation, relate_previous_play_partial, relate_previous_play_other_viewer],
    ("sql.cte.order_line_reconciliation", 1): [relate_row_permutation, relate_reconciliation_header_duplicate, relate_reconciliation_line_duplicate],
    ("sql.retention.saas_repeat_payment", 1): [relate_row_permutation, relate_repeat_payment_duplicate, relate_repeat_payment_prior_cohort],
    ("sql.temporal.clinic_weekly_visits", 1): [relate_row_permutation, relate_weekly_visit_duplicate, relate_weekly_visit_cancelled],
    ("sql.joins.logistics_final_leg", 1): [relate_row_permutation, relate_final_leg_duplicate, relate_final_leg_undelivered],
    ("sql.joins.saas_paid_invoices", 1): [relate_row_permutation, relate_add_irrelevant_account, relate_paid_invoice_duplicate, relate_paid_inactive_account],
    ("sql.subqueries.exists", 2): [relate_row_permutation, relate_add_irrelevant_customer, relate_exists_order_duplicate, relate_exists_customer_duplicate],
    ("sql.funnel.saas_activation_payment", 2): [relate_row_permutation, relate_saas_later_payment, relate_saas_incomplete_entity, relate_saas_excluded_group],
    ("sql.aggregation.manufacturing_line_scrap", 1): [relate_row_permutation, relate_scrap_additivity, relate_scrap_excluded_row],
}


def relations_for_family(family: str) -> list[RelationFn]:
    try:
        return RELATION_REGISTRY[family]
    except KeyError as exc:
        raise OracleError(f"no metamorphic relations registered for family {family!r}") from exc


def run_metamorphic_checks(ctx: MetamorphicContext) -> MetamorphicResult:
    outcomes: list[MetamorphicOutcome] = []
    relations = TEMPLATE_RELATION_OVERRIDES.get((ctx.task.template_id, ctx.task.template_version)) or TEMPLATE_RELATION_OVERRIDES.get(ctx.task.template_id)
    if relations is None:
        relations = relations_for_family(ctx.task.family)
    for fn in relations:
        try:
            outcome = fn(ctx)
        except BackendError:
            raise
        except Exception as exc:  # noqa: BLE001 — relation faults are data
            outcome = MetamorphicOutcome(
                relation_id=getattr(fn, "__name__", "unknown").upper(),
                applicable=True,
                passed=False,
                detail=f"relation error: {exc}"[:300],
            )
        outcomes.append(outcome)
    applicable = [o for o in outcomes if o.applicable]
    return MetamorphicResult(
        applicable=len(applicable),
        passed=sum(1 for o in applicable if o.passed),
        failed=sum(1 for o in applicable if not o.passed),
        outcomes=outcomes,
    )
