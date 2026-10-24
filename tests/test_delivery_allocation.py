"""Seed/format-only variations are not evidence of another business question."""
from verified_data_factory.quality.duplicate_detection import sql_fingerprint
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.qualification.lowest_quote_profile import REFERENCE


def test_lowest_quote_seed_changes_identity_not_business_instruction():
    template = load_builtin_registry().get("sql.dedup.lowest_quote", 1)
    first, second = (generate_task(template, seed) for seed in (1, 43))
    assert first.task_id != second.task_id
    assert first.instruction == second.instruction
    assert first.requirements == second.requirements
    assert first.schema_ == second.schema_
    assert sql_fingerprint(REFERENCE) == sql_fingerprint("-- same task\n" + REFERENCE + ";")
