"""Batch + serialization tests for Generation."""

import json

from verified_data_factory.generation import (
    FakeProvider,
    GenerationConfig,
    TransientProviderError,
    candidate_from_json,
    candidate_to_json,
    generate_for_tasks,
    read_candidates_jsonl,
    write_candidates_jsonl,
)
from verified_data_factory.task_engine import canonical_json, generate_task

CONFIG = GenerationConfig()


def test_batch_preserves_identity_and_order(registry):
    tasks = [generate_task(registry.get("sql.joins.simple"), seed=s) for s in (101, 102, 103)]
    results = generate_for_tasks(tasks, [FakeProvider()], CONFIG)
    assert len(results) == 3
    assert [r.candidate_solution.task_id for r in results] == [t.task_id for t in tasks]


def test_batch_partial_failures(registry):
    tasks = [generate_task(registry.get("sql.joins.simple"), seed=s) for s in (101, 102)]
    script = ["SELECT 1;", TransientProviderError("down")]
    results = generate_for_tasks(tasks, [FakeProvider(script=script)], CONFIG)
    assert results[0].generation_status == "success"
    assert results[1].generation_status == "provider_failed"
    assert results[1].candidate_solution is None


def test_batch_multi_provider(registry):
    task = generate_task(registry.get("sql.dedup.latest"), seed=801)
    providers = [FakeProvider(model_id="m-a"), FakeProvider(model_id="m-b")]
    results = generate_for_tasks(tasks=[task], providers=providers, config=CONFIG)
    assert len(results) == 2
    assert {r.candidate_solution.model for r in results} == {"m-a", "m-b"}


def test_tasks_immutable_across_generation(registry):
    tasks = [generate_task(registry.get("sql.cte.monthly"), seed=401)]
    before = canonical_json(tasks[0])
    generate_for_tasks(tasks, [FakeProvider()], CONFIG, num_candidates=2)
    assert canonical_json(tasks[0]) == before


def test_candidate_json_round_trip(registry):
    from verified_data_factory.generation import generate_candidate

    task = generate_task(registry.get("sql.windows.ranked"), seed=601)
    candidate = generate_candidate(task, FakeProvider(), CONFIG).candidate_solution
    assert candidate is not None
    blob = candidate_to_json(candidate)
    data = json.loads(blob)
    assert "is_correct" not in data
    assert data["prompt_version"] == "sql-v2"
    assert candidate_from_json(blob).candidate_id == candidate.candidate_id


def test_candidate_jsonl_round_trip(registry, tmp_path):
    from verified_data_factory.generation import generate_candidate

    candidates = []
    for seed in (101, 201, 301, 401, 501, 601, 701, 801, 901, 1001):
        template = registry.list()[0]
        task = generate_task(template, seed)
        candidate = generate_candidate(task, FakeProvider(), CONFIG).candidate_solution
        assert candidate is not None
        candidates.append(candidate)
    path = write_candidates_jsonl(candidates, tmp_path / "c.jsonl")
    restored = read_candidates_jsonl(path)
    assert [c.candidate_id for c in restored] == [c.candidate_id for c in candidates]
