"""Frozen subset API rejects invalid allocations before creating run artifacts."""
import pytest

from scripts.company_generation_experiment import freeze


@pytest.mark.parametrize("tasks,count", [
    ((), 3),
    ((("sql.dedup.lowest_quote", 1),) * 2, 3),
    ((("sql.dedup.lowest_quote", 1),), True),
    ((("sql.dedup.lowest_quote", 1),), 4),
    (tuple((f"unqualified{i}", 1) for i in range(21)), 3),
])
def test_invalid_subset_freeze_never_creates_destination(tmp_path, tasks, count):
    destination = tmp_path / "run"
    with pytest.raises(ValueError):
        freeze(destination, cpu=True, tasks=tasks, candidates_per_task=count)
    assert not destination.exists()
