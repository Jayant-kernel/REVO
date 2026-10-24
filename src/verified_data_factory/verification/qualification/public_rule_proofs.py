"""Source-bound canonical discriminators for explicitly supported public versions.

The validator independently reconstructs the SQL/fixture attribution. Execution
replay remains mandatory; profile classifications alone never certify a receipt.
"""
from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from typing import Any

import duckdb

from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.task_engine.models import TaskInstance

from ..behavior_authority import SUPPORTED_GRANULAR


def public_proofs(task: TaskInstance) -> tuple[str, dict[str, Any]]:
    if (task.template_id, task.template_version) not in SUPPORTED_GRANULAR:
        raise ValueError("granular public instruction behavior coverage unresolved")
    # Qualification tools are loaded only for this optional, source-locked replay.
    audit = import_module("scripts.engineering_rule_audit")
    references = import_module("scripts.phase3_diagnostic")
    sql: str = references._reference_sql()[task.template_id]
    pair = task.template_id, task.template_version
    from .delivery_profiles import get_profile, public_specs

    profile_module = get_profile(*pair)
    if profile_module is not None:
        return sql, public_specs(profile_module, sql)
    if pair == ("sql.dedup.lowest_quote", 1):
        from .lowest_quote_profile import proofs as quote_proofs

        return sql, quote_proofs(sql)
    if pair == ("sql.cte.inventory_net_flow", 2):
        from .inventory_flow_profile import proofs as inventory_proofs

        return sql, inventory_proofs(sql)
    if pair == ("sql.subqueries.education_all_required", 1):
        from .required_courses_profile import proofs as required_proofs

        return sql, required_proofs(sql)
    if pair == ("sql.aggregation.warehouse_throughput", 2):
        from .throughput_profile import proofs as throughput_proofs

        return sql, throughput_proofs(sql)
    if pair == ("sql.dedup.education_grade_revisions", 2):
        from .grade_revisions_profile import proofs as grade_proofs

        return sql, grade_proofs(sql)
    if pair == ("sql.aggregation.support_sla_breaches", 1):
        from .support_breaches_profile import proofs as support_proofs

        return sql, support_proofs(sql)
    if pair == ("sql.windows.media_previous_play", 1):
        from .previous_play_profile import proofs as previous_proofs

        return sql, previous_proofs(sql)
    if pair == ("sql.cte.order_line_reconciliation", 1):
        from .reconciliation_profile import proofs as reconciliation_proofs

        return sql, reconciliation_proofs(sql)
    if pair == ("sql.retention.saas_repeat_payment", 1):
        from .repeat_payment_profile import proofs as retention_proofs

        return sql, retention_proofs(sql)
    if pair == ("sql.temporal.clinic_weekly_visits", 1):
        from .weekly_visits_profile import proofs as weekly_proofs

        return sql, weekly_proofs(sql)
    if pair == ("sql.joins.logistics_final_leg", 1):
        from .final_leg_profile import proofs as final_leg_proofs

        return sql, final_leg_proofs(sql)
    if pair == ("sql.joins.saas_paid_invoices", 1):
        from .paid_invoices_profile import proofs as paid_proofs

        return sql, paid_proofs(sql)
    if pair == ("sql.subqueries.exists", 2):
        from .exists_profile import proofs as exists_proofs

        return sql, exists_proofs(sql)
    if pair == ("sql.aggregation.fulfillment_sla_dashboard", 1):
        from .sla_profile import proofs

        return sql, proofs(sql)
    if pair == ("sql.funnel.saas_activation_payment", 2):
        profile = audit.saas_profile
    elif pair == ("sql.aggregation.manufacturing_line_scrap", 1):
        profile = audit.scrap_profile
    else:
        raise ValueError("unsupported public proof contract/version")
    return sql, profile(task, sql, execute=False)


def schema_checks(task: TaskInstance, table_name: str, column_name: str) -> dict[str, Any]:
    """Execute declared type checks separately from NOT NULL rejection.

    VARCHAR has no invalid non-null value in this public coercive SQL domain.
    No unstated positivity, enum or uniqueness restrictions are introduced.
    """
    column = next(c for t in task.schema_ if t.name == table_name for c in t.columns
                  if c.name == column_name)
    con = materialize_duckdb(task.schema_, task.tables)
    try:
        descriptions = con.execute(f'DESCRIBE "{table_name}"').fetchall()
        actual = next(row for row in descriptions if row[0] == column_name)
        result: dict[str, Any] = {"type": actual[1], "nullable": actual[2], "declared_type": column.type,
                   "domain_reason": "Declared SQL type and declared nullability only; no additional restrictions."}
        from .delivery_profiles import get_profile

        profile_module = get_profile(task.template_id, task.template_version)
        if profile_module is not None:
            if actual[1] != column.type or actual[2] != ("YES" if column.nullable else "NO"):
                raise ValueError("declared type/nullability mismatch")
            result.update(profile_module.schema_checks(task, table_name, column_name))
            return result
        if (task.template_id, task.template_version) == ("sql.dedup.lowest_quote", 1):
            from .lowest_quote_profile import quote, validate_rows

            invalid_values = [True, False, "10", 1.5, -1, 2147483648] if column_name == "price_cents" else [42, True, None]
            rejections = []
            for value in invalid_values:
                row = quote()
                row[column_name] = value
                try:
                    validate_rows({"quotes": [row]})
                except ValueError as exc:
                    rejections.append({"value": value, "reason": str(exc)})
                else:
                    raise ValueError("raw lowest-quote domain probe was not rejected")
            valid_values = [None, 0, 2147483647] if column_name == "price_cents" else ["", "A", "a", "é", " s "]
            for value in valid_values:
                row = quote()
                row[column_name] = value
                validate_rows({"quotes": [row]})
            result.update(domain_reason="Exact non-coercing lowest_quote@1 text/integer-cents domain",
                          raw_rejections=rejections, raw_conformance=valid_values)
            return result
        if actual[1] == "VARCHAR":
            result["invalid_type"] = "not applicable: every non-null SQL VARCHAR value is in the declared domain"
            result["conversion"] = con.execute("SELECT CAST(42 AS VARCHAR)").fetchone()[0]
        else:
            try:
                con.execute(f"SELECT CAST('not-a-valid-value' AS {actual[1]})").fetchall()
            except duckdb.ConversionException as exc:
                result["invalid_type"] = type(exc).__name__
            else:
                raise ValueError("declared type probe was not rejected")
        if actual[1] != column.type or actual[2] != ("YES" if column.nullable else "NO"):
            raise ValueError("declared type/nullability mismatch")
        return result
    finally:
        con.close()


def schema_invalid(task: TaskInstance, table_name: str, column_name: str) -> dict[str, list[dict[str, Any]]]:
    tables = deepcopy(task.tables)
    tables[table_name][0][column_name] = None
    return tables
