"""Registry tests: registration, retrieval, listing, duplicates, bad files."""

import pytest

from verified_data_factory.task_engine.errors import RegistryError, TemplateError
from verified_data_factory.task_engine.registry import TemplateRegistry


def test_registry_lists_all_templates(registry):
    assert len(registry) == 23


def test_registry_get(registry):
    t = registry.get("sql.aggregation.grouped")
    assert t.family == "aggregation"
    assert t.difficulty in (1, 2, 3, 4, 5)


def test_registry_get_unknown_raises(registry):
    with pytest.raises(RegistryError):
        registry.get("sql.nope.missing")


def test_registry_list_by_family(registry):
    assert len(registry.list_by_family("retention")) == 2
    assert registry.list_by_family("retention")[0].template_id == "sql.retention.30_day"
    assert registry.list_by_family("no_such_family") == []


def test_registry_metadata_shape(registry):
    for entry in registry.metadata():
        assert set(entry) == {"template_id", "version", "family", "difficulty", "description"}


def test_registry_duplicate_rejected(registry):
    dup = registry.get("sql.joins.simple")
    fresh = TemplateRegistry()
    fresh.register(dup)
    with pytest.raises(RegistryError):
        fresh.register(dup)


def test_registry_rejects_malformed_yaml(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("{{{{ not: [valid yaml", encoding="utf-8")
    fresh = TemplateRegistry()
    with pytest.raises((TemplateError, RegistryError)):
        fresh.load_file(bad)
