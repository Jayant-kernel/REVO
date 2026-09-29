"""Prompt tests: public content in, verification internals out."""

from verified_data_factory.generation import build_solver_context, build_sql_prompt
from verified_data_factory.task_engine import generate_task


def _task(registry):
    return generate_task(registry.get("sql.retention.30_day"), seed=901)


def test_prompt_includes_public_content(registry):
    task = _task(registry)
    prompt = build_sql_prompt(task)
    assert "DuckDB" in prompt
    assert task.instruction in prompt
    assert "CREATE TABLE" in prompt
    assert "customers" in prompt and "events" in prompt
    assert "only the SQL query" in prompt
    assert "Public output contract" in prompt
    assert '"output_columns"' in prompt


def test_prompt_excludes_oracle_and_verification(registry):
    task = _task(registry)
    prompt = build_sql_prompt(task)
    lowered = prompt.lower()
    assert "oracle" not in lowered
    assert "hidden" not in lowered
    assert "mutation" not in lowered
    assert "verdict" not in lowered
    assert task.oracle_spec.strategy not in prompt
    assert task.oracle_spec.type not in prompt


def test_prompt_excludes_fixture_rows(registry):
    task = _task(registry)
    prompt = build_sql_prompt(task)
    # Real cell values from the fixture must never appear.
    sample_names = [r["name"] for r in task.tables["customers"][:3]]
    for name in sample_names:
        assert name not in prompt
    sample_times = [r["event_time"] for r in task.tables["events"][:3]]
    for stamp in sample_times:
        assert stamp not in prompt
    assert "generation_metadata" not in prompt
    assert "fixture_metadata" not in prompt


def test_prompt_excludes_internal_metadata(registry):
    task = _task(registry)
    ctx = build_solver_context(task)
    assert set(ctx.model_dump()) == {
        "task_id",
        "dialect",
        "ddl",
        "instruction",
        "requirements",
        "prompt_version",
    }
    prompt = build_sql_prompt(task)
    # Minimal solver surface: internal ids stay out of the model input;
    # traceability lives in SolverContext + CandidateSolution instead.
    assert task.task_id not in prompt
    assert ctx.task_id == task.task_id


def test_prompt_is_deterministic(registry):
    task = _task(registry)
    assert build_sql_prompt(task) == build_sql_prompt(task)


def test_task_not_mutated_by_prompt(registry):
    from verified_data_factory.task_engine import canonical_json

    task = _task(registry)
    before = canonical_json(task)
    build_sql_prompt(task)
    build_solver_context(task)
    assert canonical_json(task) == before


def test_prompt_output_contract_is_public_but_not_verification_metadata(registry):
    task = generate_task(registry.get("sql.aggregation.grouped"), seed=301)
    prompt = build_sql_prompt(task)
    assert '"avg_amount"' in prompt
    assert "oracle_spec" not in prompt
    assert "fixture_metadata" not in prompt
