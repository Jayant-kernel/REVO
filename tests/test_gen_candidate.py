"""Candidate tests: binding, parser provenance, identity, no verdict fields."""

from verified_data_factory.generation import (
    FakeProvider,
    GenerationConfig,
    build_candidate_id,
    generate_candidate,
    generate_candidates,
)
from verified_data_factory.task_engine import generate_task

CONFIG = GenerationConfig(temperature=0.4, top_p=0.95, max_tokens=2048, seed=7)


def _task(registry):
    return generate_task(registry.get("sql.aggregation.grouped"), seed=301)


def test_candidate_bound_to_task(registry):
    task = _task(registry)
    result = generate_candidate(task, FakeProvider(), CONFIG)
    assert result.generation_status == "success"
    candidate = result.candidate_solution
    assert candidate is not None
    assert candidate.task_id == task.task_id
    assert candidate.prompt_version == "sql-v2"
    assert candidate.generation_schema_version == "1.0"
    assert candidate.generation_config == CONFIG


def test_sql_comes_from_raw_through_parser(registry):
    task = _task(registry)
    raw = "Here you go:\n```sql\nSELECT status, COUNT(*) FROM orders GROUP BY status;\n```"
    result = generate_candidate(task, FakeProvider(script=[raw]), CONFIG)
    candidate = result.candidate_solution
    assert candidate is not None
    assert candidate.raw_response == raw
    assert candidate.candidate_sql == "SELECT status, COUNT(*) FROM orders GROUP BY status"
    assert result.parse_status == "success"


def test_no_correctness_fields_exist(registry):
    task = _task(registry)
    candidate = generate_candidate(task, FakeProvider(), CONFIG).candidate_solution
    assert candidate is not None
    dumped = candidate.model_dump()
    for banned in ("is_correct", "verification_status", "test_status", "score", "verdict"):
        assert banned not in dumped
        assert not hasattr(candidate, banned)


def test_candidate_identity_deterministic_and_sensitive(registry):
    task = _task(registry)
    a = generate_candidate(task, FakeProvider(), CONFIG).candidate_solution
    b = generate_candidate(task, FakeProvider(), CONFIG).candidate_solution
    assert a is not None and b is not None
    assert a.candidate_id == b.candidate_id
    other_seed = GenerationConfig(temperature=0.4, top_p=0.95, max_tokens=2048, seed=8)
    c = generate_candidate(task, FakeProvider(), other_seed).candidate_solution
    assert c is not None
    assert c.candidate_id != a.candidate_id
    d = generate_candidate(task, FakeProvider(), CONFIG, candidate_index=1).candidate_solution
    assert d is not None
    assert d.candidate_id != a.candidate_id
    assert a.candidate_id.startswith(task.task_id)


def test_build_candidate_id_direct():
    assert build_candidate_id("t", "m", "r", "p", CONFIG, 0) == build_candidate_id(
        "t", "m", "r", "p", CONFIG, 0
    )


def test_provenance_without_secrets(registry):
    task = _task(registry)
    fake = FakeProvider(model_id="Qwen/Qwen3-Coder-30B-A3B-Instruct")
    candidate = generate_candidate(task, fake, CONFIG).candidate_solution
    assert candidate is not None
    assert candidate.model == "Qwen/Qwen3-Coder-30B-A3B-Instruct"
    assert candidate.provider == "fake"
    assert candidate.endpoint_id.startswith("fake:")
    blob = candidate.model_dump_json()
    assert "api_key" not in blob.lower()
    assert "bearer" not in blob.lower()


def test_provider_failure_is_data(registry):
    from verified_data_factory.generation import TransientProviderError

    task = _task(registry)
    result = generate_candidate(task, FakeProvider(script=[TransientProviderError("x")]), CONFIG)
    assert result.generation_status == "provider_failed"
    assert result.candidate_solution is None
    assert result.failure_reason is not None


def test_parse_failure_is_data(registry):
    task = _task(registry)
    result = generate_candidate(task, FakeProvider(script=["no sql here"]), CONFIG)
    assert result.generation_status == "success"
    assert result.parse_status == "failed"
    candidate = result.candidate_solution
    assert candidate is not None
    assert candidate.candidate_sql is None
    assert candidate.raw_response == "no sql here"


def test_multiple_candidates_isolated(registry):
    task = _task(registry)
    results = generate_candidates(
        task,
        [FakeProvider(script=["SELECT 1;", "garbage", "SELECT 3;"])],
        CONFIG,
        num_candidates=3,
    )
    assert [r.parse_status for r in results] == ["success", "failed", "success"]
    ids = [r.candidate_solution.candidate_id for r in results if r.candidate_solution]
    assert len(set(ids)) == 3
