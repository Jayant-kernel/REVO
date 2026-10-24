"""INTEGER input products may exceed INTEGER; neither overflow nor float rounding is valid."""
from scripts.phase3_diagnostic import _reference_sql
from tests.test_stage5_sla_profile import matches
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.qualification import (
    reconciliation_profile as reconciliation,
)


def test_reconciliation_reference_covers_declared_integer_products():
    task = generate_task(load_builtin_registry().get(reconciliation.CONTRACT, 1), 94001)
    assert matches(task, _reference_sql()[reconciliation.CONTRACT], reconciliation.rich_fixture())
