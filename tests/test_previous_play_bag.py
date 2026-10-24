"""Equal output IDs can have different NULL/integer histories across partitions."""
from scripts.phase3_diagnostic import _reference_sql
from tests.test_stage5_sla_profile import matches
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.qualification import previous_play_profile as previous


def test_previous_play_repeated_ids_do_not_impose_extra_output_tie_order():
    task = generate_task(load_builtin_registry().get(previous.CONTRACT, 1), 94001)
    assert matches(task, _reference_sql()[previous.CONTRACT], previous.rich_fixture())
