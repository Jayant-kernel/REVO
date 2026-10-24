"""V2 enforces the approved domain; historical V1 remains unchanged."""
from copy import deepcopy

import pytest

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.oracle_registry import get_oracle
from verified_data_factory.verification.qualification.grade_revisions_profile import (
    CONTRACT,
    revision,
    rich_fixture,
)


def test_grade_v2_conflicting_valid_identity_is_rejected_and_exact_repeat_allowed():
    task = generate_task(load_builtin_registry().get(CONTRACT, 2), 94001)
    rows = [revision(1, grade="A"), revision(1, grade="B")]
    with pytest.raises(ValueError, match="conflicting valid grades"):
        get_oracle(CONTRACT, 2).fn(task.requirements, {"grade_revisions": rows})
    legacy = generate_task(load_builtin_registry().get(CONTRACT, 1), 94001)
    assert get_oracle(CONTRACT, 1).fn(legacy.requirements, {"grade_revisions": rows}).rows[0][2] == "A"
    repeated = {"grade_revisions": [revision(1, grade="A"), revision(1, grade="A")]}
    assert len(get_oracle(CONTRACT, 2).fn(task.requirements, repeated).rows) == 1


def test_grade_v2_normalizes_timestamp_identity_and_ignores_cancelled_conflicts():
    task = generate_task(load_builtin_registry().get(CONTRACT, 2), 94001)
    rows = [revision(1, at="2025-01-01 00:00:00", grade="A"),
            revision(1, at="2025-01-01T00:00:00", grade="B")]
    with pytest.raises(ValueError, match="conflicting"):
        get_oracle(CONTRACT, 2).fn(task.requirements, {"grade_revisions": rows})
    rows[1]["revision_status"] = "cancelled"
    assert get_oracle(CONTRACT, 2).fn(task.requirements, {"grade_revisions": rows}).rows[0][2] == "A"
    tables = rich_fixture()
    original = get_oracle(CONTRACT, 2).fn(task.requirements, tables).model_dump(mode="json")
    reversed_tables = deepcopy(tables)
    reversed_tables["grade_revisions"].reverse()
    assert get_oracle(CONTRACT, 2).fn(task.requirements, reversed_tables).model_dump(mode="json") == original
