"""Task identity tests: stable, collision-resistant, input-sensitive ids."""

from verified_data_factory.task_engine import generate_task
from verified_data_factory.task_engine.seed import build_task_id


def test_same_inputs_same_id():
    kwargs = {
        "template_id": "sql.retention.30_day",
        "template_version": 1,
        "seed": 12345,
        "config": {"retention_window_days": 30},
    }
    assert build_task_id(**kwargs) == build_task_id(**kwargs)


def test_different_seeds_different_ids():
    a = build_task_id("sql.retention.30_day", 1, 12345, {})
    b = build_task_id("sql.retention.30_day", 1, 12346, {})
    assert a != b


def test_large_seeds_do_not_collide():
    # The old `seed % 1M` scheme collided here; the hash scheme must not.
    a = build_task_id("sql.retention.30_day", 1, 12345, {})
    b = build_task_id("sql.retention.30_day", 1, 12345 + 1_000_000, {})
    assert a != b


def test_different_versions_different_ids():
    a = build_task_id("sql.retention.30_day", 1, 42, {})
    b = build_task_id("sql.retention.30_day", 2, 42, {})
    assert a != b


def test_different_configs_different_ids():
    a = build_task_id("sql.retention.30_day", 1, 42, {"year": 2025})
    b = build_task_id("sql.retention.30_day", 1, 42, {"year": 2026})
    assert a != b


def test_config_order_independent():
    a = build_task_id("sql.joins.simple", 1, 7, {"b": 1, "a": 2})
    b = build_task_id("sql.joins.simple", 1, 7, {"a": 2, "b": 1})
    assert a == b


def test_config_override_changes_task_id(registry):
    template = registry.get("sql.joins.simple")
    base = generate_task(template, 101)
    altered = generate_task(template, 101, {"year": 2026})
    assert base.task_id != altered.task_id


def test_no_collisions_across_catalog(registry):
    from tests.conftest import catalog_entries
    from verified_data_factory.task_engine import generate_batch

    ids = []
    for entry in catalog_entries():
        template = registry.get(entry["template_id"], entry.get("version"))
        ids.extend(t.task_id for t in generate_batch(template, list(entry["seeds"])))
    assert len(ids) == 100
    assert len(set(ids)) == 100
