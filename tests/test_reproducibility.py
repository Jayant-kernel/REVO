"""Reproducibility tests: the seed-replay contract (mandatory).

Invariant (not every field must differ across seeds)::

    same seed -> same task
    different seeds -> independently generated valid instances
"""

import re

import pytest

from verified_data_factory.task_engine import (
    canonical_hash,
    canonical_json,
    generate_task,
    validate_task,
)

# Representative seed set: boundaries, small values, typical, large, huge.
SEED_SET = [0, 1, 2, 42, 12345, 999999, 2**63 - 1]

TASK_ID_RE = re.compile(r"^sql\.[a-z0-9_.]+\.v\d+\.[0-9a-f]{12}$")


def test_same_seed_same_canonical_task(registry):
    for template in registry.list():
        a = generate_task(template, seed=12345)
        b = generate_task(template, seed=12345)
        assert canonical_json(a) == canonical_json(b)
        assert canonical_hash(a) == canonical_hash(b)


def test_different_seed_meaningfully_different(registry):
    for template in registry.list():
        a = generate_task(template, seed=12345)
        b = generate_task(template, seed=12346)
        assert canonical_hash(a) != canonical_hash(b)
        # Row content (not just metadata) must differ somewhere.
        assert a.tables != b.tables, f"{template.template_id} identical across seeds"


def test_task_id_format_and_stability(registry):
    template = registry.get("sql.retention.30_day")
    a = generate_task(template, seed=12345)
    b = generate_task(template, seed=12345)
    assert TASK_ID_RE.match(a.task_id), a.task_id
    assert a.task_id.startswith("sql.retention.30_day.v2.")
    assert a.task_id == b.task_id


@pytest.mark.parametrize("seed", SEED_SET)
def test_seed_set_replay_and_validity(registry, seed):
    """Every representative seed replays exactly and stays valid."""
    for template in registry.list():
        a = generate_task(template, seed=seed)
        b = generate_task(template, seed=seed)
        assert canonical_json(a) == canonical_json(b)
        assert TASK_ID_RE.match(a.task_id)
        validate_task(a)  # relationships, schema, id binding hold
        assert {t.name for t in a.schema_} == {t.name for t in template.schema_definition}


def test_seed_set_gives_independent_instances(registry):
    """Across the seed set: unique ids and real fixture variation."""
    template = registry.get("sql.retention.30_day")
    tasks = [generate_task(template, seed=s) for s in SEED_SET]
    ids = [t.task_id for t in tasks]
    assert len(set(ids)) == len(tasks)
    variants = {canonical_hash(t) for t in tasks}
    assert len(variants) == len(tasks)
