"""Signed INTEGER corrections must widen before issue negation, not after SUM."""
import pytest

from scripts.phase3_diagnostic import _reference_sql
from tests.test_stage5_sla_profile import matches
from verified_data_factory.task_engine import generate_task, load_builtin_registry


@pytest.mark.parametrize("receipt_units,issue_units", [(None, -2147483648), (-2147483648, None), (2147483647, -2147483648)])
def test_declared_integer_extremes_match_unbounded_inventory_oracle(receipt_units, issue_units):
    task = generate_task(load_builtin_registry().get("sql.cte.inventory_net_flow", 1), 94001)
    def movement(units):
        return {"movement_id": 1, "warehouse": "correction", "occurred_on": "2025-01-01",
                "units": units, "status": "posted"}
    tables = {"receipts": [] if receipt_units is None else [movement(receipt_units)],
              "issues": [] if issue_units is None else [movement(issue_units)]}
    assert matches(task, _reference_sql()[task.template_id], tables)
