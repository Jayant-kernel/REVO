"""Only approved v2 receives bag qualification; repeated IDs impose no uniqueness."""
import pytest

from scripts.engineering_qualification_receipts import profile
from scripts.phase3_diagnostic import _reference_sql
from tests.test_stage5_sla_profile import matches
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.oracle_registry import get_oracle
from verified_data_factory.verification.qualification.inventory_flow_profile import (
    CONTRACT,
    alternatives,
    movement,
)


def test_same_ids_with_equal_and_different_payloads_are_valid_row_bags():
    task = generate_task(load_builtin_registry().get(CONTRACT, 2), 94001)
    tables = {"receipts": [movement(1), movement(1), movement(1, units=7)],
              "issues": [movement(1, units=3), movement(1, units=3)]}
    expected = get_oracle(CONTRACT,2).fn(task.requirements,tables)
    assert expected.rows == [["A",21]]
    for sql in alternatives(_reference_sql()[CONTRACT]):
        assert matches(task,sql,tables)


def test_old_version_does_not_borrow_forward_bag_qualification(tmp_path):
    old = generate_task(load_builtin_registry().get(CONTRACT, 1), 94001)
    assert not public_behavior_map(old).granular
    with pytest.raises(ValueError, match="unsupported qualification profile"):
        profile(tmp_path,CONTRACT,1)
