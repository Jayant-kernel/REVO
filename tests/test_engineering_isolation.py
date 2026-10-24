import pytest

from tests.product_fixtures import make_golden
from verified_data_factory.products.errors import ProductConfigError
from verified_data_factory.products.isolation import (
    connected_groups,
    register_roles,
    schema_role_fingerprint,
    sql_structure_fingerprint,
)
from verified_data_factory.products.models import SplitPolicy
from verified_data_factory.products.splits import build_splits


def test_renamed_schema_and_sql_shapes_cannot_hide_overlap():
    first = make_golden(1, "aggregation")
    second = first.model_copy(update={"candidate_id": "renamed", "schema_": [{"name": "renamed_orders", "columns": [
        {"name": "renamed_id", "type": "INTEGER", "nullable": False}, {"name": "renamed_amount", "type": "DOUBLE", "nullable": True}]}],
        "candidate_solution": "SELECT * FROM renamed_orders WHERE renamed_id > 999;"})
    assert schema_role_fingerprint(first.schema_) == schema_role_fingerprint(second.schema_)
    assert sql_structure_fingerprint(first.candidate_solution) == sql_structure_fingerprint(second.candidate_solution)
    groups = connected_groups([first, second])
    assert groups[first.candidate_id] == groups[second.candidate_id]


def test_missing_engineering_group_fails_closed():
    with pytest.raises(ProductConfigError, match="metadata missing"):
        build_splits([make_golden(1, "aggregation")], {}, SplitPolicy(group_by="engineering_group"))


def test_inconsistent_group_metadata_cannot_bypass_connected_isolation():
    goldens = [make_golden(1, "aggregation"), make_golden(2, "aggregation")]
    quality = {g.candidate_id: {"engineering_isolation_group": g.candidate_id} for g in goldens}
    with pytest.raises(ProductConfigError, match="inconsistent"):
        build_splits(goldens, quality, SplitPolicy(group_by="engineering_group"))


def test_connected_groups_remain_in_one_split():
    goldens = [make_golden(1, "aggregation"), make_golden(2, "aggregation")]
    groups = connected_groups(goldens)
    quality = {g.candidate_id: {"engineering_isolation_group": groups[g.candidate_id]} for g in goldens}
    split = build_splits(goldens, quality, SplitPolicy(group_by="engineering_group"))
    assert sum(bool(s.candidate_ids) for s in split.values()) == 1


def test_cross_product_role_registry_rejects_overlap(tmp_path):
    path = tmp_path / "roles.json"
    register_roles(path, [make_golden(1, "aggregation")], "TRAIN")
    before = path.read_bytes()
    with pytest.raises(ProductConfigError, match="crosses"):
        register_roles(path, [make_golden(2, "aggregation")], "EVAL")
    assert path.read_bytes() == before
