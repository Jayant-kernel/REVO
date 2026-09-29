"""Regression coverage for confirmed Pilot-001 task-specification defects."""

from verified_data_factory.task_engine import generate_task


def test_aggregation_names_every_output_alias(registry):
    instruction = generate_task(registry.get("sql.aggregation.grouped", 2), 1301).instruction
    assert "AVG(amount) AS avg_amount" in instruction
    assert "Return exactly the columns" in instruction


def test_month_tasks_require_yyyy_mm_strings(registry):
    cte = generate_task(registry.get("sql.cte.monthly", 2), 1401).instruction
    temporal = generate_task(registry.get("sql.temporal.monthly", 2), 1701).instruction
    assert "VARCHAR formatted exactly YYYY-MM" in cte
    assert "VARCHAR formatted exactly YYYY-MM" in temporal


def test_dedup_excludes_event_type_from_winner_partition(registry):
    instruction = generate_task(registry.get("sql.dedup.latest", 2), 1801).instruction
    assert "exactly one row per customer" in instruction
    assert "do not partition by event_type" in instruction


def test_funnel_requires_customers_without_events(registry):
    instruction = generate_task(registry.get("sql.funnel.completion", 2), 1101).instruction
    assert "including customers with no events" in instruction
    assert "do not calculate a session id" in instruction


def test_v3_month_contracts_are_explicit_and_do_not_leak_oracles(registry):
    cte_task = generate_task(registry.get("sql.cte.monthly", 3), 1401)
    temporal_task = generate_task(registry.get("sql.temporal.monthly", 3), 1701)
    for instruction in (cte_task.instruction, temporal_task.instruction):
        assert "valid DuckDB SQL" in instruction
        assert "DATE_FORMAT" in instruction
        assert "TO_CHAR" in instruction
        assert "VARCHAR formatted exactly YYYY-MM" in instruction
        assert "oracle" not in instruction.lower()
        assert "reference_query" not in instruction
        assert "expected" not in instruction.lower()


def test_v2_is_unchanged_and_v3_has_distinct_identity(registry):
    v2 = generate_task(registry.get("sql.cte.monthly", 2), 1401)
    v2_replay = generate_task(registry.get("sql.cte.monthly", 2), 1401)
    v3 = generate_task(registry.get("sql.cte.monthly", 3), 1401)
    assert v2 == v2_replay
    assert v2.task_id != v3.task_id
    assert v2.template_version == 2
    assert v3.template_version == 3


def test_v4_month_contracts_pin_duckdb_argument_order_and_temporal_aliases(registry):
    cte = generate_task(registry.get("sql.cte.monthly", 4), 1401)
    temporal = generate_task(registry.get("sql.temporal.monthly", 4), 1701)
    assert "strftime('%Y-%m', CAST(order_date AS DATE))" in cte.instruction
    assert "Never reverse the strftime arguments" in cte.instruction
    assert "strftime('%Y-%m', CAST(event_time AS DATE))" in temporal.instruction
    assert "COALESCE(o.activity_month, e.activity_month) AS activity_month" in temporal.instruction
    assert "Never select an unqualified activity_month" in temporal.instruction
    assert cte.task_id != generate_task(registry.get("sql.cte.monthly", 3), 1401).task_id
    assert temporal.task_id != generate_task(registry.get("sql.temporal.monthly", 3), 1701).task_id


def test_v5_temporal_contract_pins_both_window_predicates(registry):
    v4 = generate_task(registry.get("sql.temporal.monthly", 4), 1701)
    v5 = generate_task(registry.get("sql.temporal.monthly", 5), 1701)
    assert "order_date >= DATE '2025-01-01' AND order_date < DATE '2025-04-01'" in v5.instruction
    assert "event_time >= TIMESTAMP '2025-01-01 00:00:00' AND event_time < TIMESTAMP '2025-04-01 00:00:00'" in v5.instruction
    assert "required_order_window_predicate" in v5.requirements
    assert "required_event_window_predicate" in v5.requirements
    assert v5.task_id != v4.task_id
