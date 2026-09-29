"""Release build / validate / load / diff tests (Phase 7, §22–§31, §35–§37)."""

import json

import pytest

from tests.product_fixtures import build_product_fixture
from verified_data_factory.products import (
    ProductConfig,
    SplitPolicy,
    build_release,
    diff_releases,
    load_release,
    validate_release,
)
from verified_data_factory.products.errors import ProductValidationError
from verified_data_factory.products.release import SAMPLE_RECORD_LIMIT


def _build(tmp_path, name="p", out_name=None, **overrides):
    goldens, quality_by_id, snapshot = build_product_fixture()
    config = ProductConfig(
        product_name=name, product_type="TRAIN", visibility="INTERNAL", **overrides
    )
    built = build_release(
        snapshot=snapshot,
        golden_records=goldens,
        quality_by_id=quality_by_id,
        config=config,
        out_dir=tmp_path / (out_name or name),
        factory_version="0.7.0",
        provenance_version="1.0",
        quarantined_ids=set(),
        supply_chain={"commercially_cleared": True},
    )
    return built, goldens, quality_by_id, snapshot


def test_content_hash_snapshot_resolves(tmp_path):
    """CLI-built bundles carry content-hash membership; releases must resolve it."""
    from verified_data_factory.provenance import build_dataset_snapshot
    from verified_data_factory.provenance.nodes import golden_record_node

    goldens, quality_by_id, _ = build_product_fixture()
    content_ids = sorted(golden_record_node(g).payload["golden_content_hash"] for g in goldens)
    snapshot = build_dataset_snapshot(content_ids, "content-hash-set", "1.0", "sel-1", "5.0")
    built, _, _, _ = _build(tmp_path, name="ch")
    rebuilt = build_release(
        snapshot=snapshot,
        golden_records=goldens,
        quality_by_id=quality_by_id,
        config=ProductConfig(product_name="ch", product_type="TRAIN", visibility="INTERNAL"),
        out_dir=tmp_path / "ch2",
        factory_version="0.7.0",
        provenance_version="1.0",
    )
    assert rebuilt.manifest.record_count == built.manifest.record_count > 0
    assert rebuilt.validation.status == "VALID"


def test_empty_snapshot_membership_rejected(tmp_path):
    from verified_data_factory.products.errors import ProductConfigError
    from verified_data_factory.provenance import build_dataset_snapshot

    goldens, quality_by_id, _ = build_product_fixture()
    snapshot = build_dataset_snapshot(["sha256:deadbeef"], "empty-set", "1.0", "sel-1", "5.0")
    with pytest.raises(ProductConfigError):
        build_release(
            snapshot=snapshot,
            golden_records=goldens,
            quality_by_id=quality_by_id,
            config=ProductConfig(product_name="e", product_type="TRAIN", visibility="INTERNAL"),
            out_dir=tmp_path / "e",
            factory_version="0.7.0",
            provenance_version="1.0",
        )


def test_train_build_is_valid_and_deterministic(tmp_path):
    # Same product content in two directories → same release id
    # (timestamps and paths never enter the identity).
    first, _, _, _ = _build(tmp_path, name="p", out_name="a")
    second, _, _, _ = _build(tmp_path, name="p", out_name="b")
    assert first.validation.status == "VALID"
    assert first.manifest.release_id == second.manifest.release_id
    assert first.manifest.record_count == first.manifest.split_counts["train"]
    assert (tmp_path / "a" / "manifest.json").exists()
    assert (tmp_path / "a" / "SHA256SUMS").exists()
    assert (tmp_path / "a" / "dataset_card.md").exists()
    assert (tmp_path / "a" / "preview.json").exists()
    assert (tmp_path / "a" / "metrics.json").exists()


def test_public_eval_withholds_targets(tmp_path):
    goldens, quality_by_id, snapshot = build_product_fixture()
    config = ProductConfig(product_name="e", product_type="PUBLIC_EVAL", visibility="PUBLIC")
    built = build_release(
        snapshot=snapshot,
        golden_records=goldens,
        quality_by_id=quality_by_id,
        config=config,
        out_dir=tmp_path / "e",
        factory_version="0.7.0",
        provenance_version="1.0",
        quarantined_ids=set(),
        supply_chain={"commercially_cleared": True},
    )
    assert built.validation.status == "VALID"
    assert goldens[10].record_id not in [
        r["golden_record_id"] for r in _all_records(tmp_path / "e")
    ]
    for record in _all_records(tmp_path / "e"):
        assert "sql" not in record


def test_private_eval_exposes_targets(tmp_path):
    goldens, quality_by_id, snapshot = build_product_fixture()
    config = ProductConfig(product_name="pv", product_type="PRIVATE_EVAL", visibility="INTERNAL")
    built = build_release(
        snapshot=snapshot,
        golden_records=goldens,
        quality_by_id=quality_by_id,
        config=config,
        out_dir=tmp_path / "pv",
        factory_version="0.7.0",
        provenance_version="1.0",
        quarantined_ids=set(),
        supply_chain={"commercially_cleared": True},
    )
    assert built.validation.status == "VALID"
    records = _all_records(tmp_path / "pv")
    assert records and all(r.get("sql") for r in records)


def test_benchmark_ids_stable(tmp_path):
    def _bench(out_name):
        goldens, quality_by_id, snapshot = build_product_fixture()
        return build_release(
            snapshot=snapshot,
            golden_records=goldens,
            quality_by_id=quality_by_id,
            config=ProductConfig(
                product_name="bench", product_type="BENCHMARK", visibility="INTERNAL"
            ),
            out_dir=tmp_path / out_name,
            factory_version="0.7.0",
            provenance_version="1.0",
        )

    first = _bench("b1")
    second = _bench("b2")
    assert first.manifest.release_id == second.manifest.release_id
    ids_first = [r["benchmark_item_id"] for r in _all_records(tmp_path / "b1")]
    ids_second = [r["benchmark_item_id"] for r in _all_records(tmp_path / "b2")]
    assert ids_first == ids_second
    assert len(set(ids_first)) == len(ids_first)


def test_sample_product_capped(tmp_path):
    goldens, quality_by_id, snapshot = build_product_fixture()
    built = build_release(
        snapshot=snapshot,
        golden_records=goldens,
        quality_by_id=quality_by_id,
        config=ProductConfig(product_name="s", product_type="SAMPLE", visibility="PUBLIC"),
        out_dir=tmp_path / "s",
        factory_version="0.7.0",
        provenance_version="1.0",
        quarantined_ids=set(),
        supply_chain={"commercially_cleared": True},
    )
    assert built.validation.status == "VALID"
    assert built.manifest.record_count <= SAMPLE_RECORD_LIMIT


def test_parquet_sharded_build_valid(tmp_path):
    goldens, quality_by_id, snapshot = build_product_fixture()
    built = build_release(
        snapshot=snapshot,
        golden_records=goldens,
        quality_by_id=quality_by_id,
        config=ProductConfig(
            product_name="pq",
            product_type="TRAIN",
            visibility="INTERNAL",
            output_format="parquet",
            shard_size=5,
        ),
        out_dir=tmp_path / "pq",
        factory_version="0.7.0",
        provenance_version="1.0",
    )
    assert built.validation.status == "VALID"
    assert built.manifest.shard_count > 1
    loaded = load_release(tmp_path / "pq")
    assert len(loaded) == built.manifest.record_count


def test_tampered_shard_fails_validation(tmp_path):
    built, _, _, _ = _build(tmp_path, name="t")
    shard = tmp_path / "t" / built.manifest.shards[0].relative_path
    shard.write_bytes(shard.read_bytes() + b"tamper\n")
    report = validate_release(tmp_path / "t")
    assert report.status == "INVALID"
    assert report.errors
    with pytest.raises(ProductValidationError):
        load_release(tmp_path / "t")


def test_missing_file_fails_validation(tmp_path):
    built, _, _, _ = _build(tmp_path, name="m")
    (tmp_path / "m" / built.manifest.shards[0].relative_path).unlink()
    report = validate_release(tmp_path / "m")
    assert report.status == "INVALID"


def test_load_release_roundtrip(tmp_path):
    built, _, _, _ = _build(tmp_path, name="r")
    loaded = load_release(tmp_path / "r")
    assert loaded.manifest.release_id == built.manifest.release_id
    assert len(loaded) == built.manifest.record_count


def test_diff_identical_releases_empty(tmp_path):
    _build(tmp_path, name="p", out_name="d1")
    _build(tmp_path, name="p", out_name="d2")
    diff = diff_releases(tmp_path / "d1", tmp_path / "d2")
    assert diff.records_added == [] and diff.records_removed == [] and diff.records_changed == []
    assert diff.config_changed is False and diff.splits_changed is False


def test_diff_detects_seed_change(tmp_path):
    goldens, quality_by_id, snapshot = build_product_fixture()
    for out_name, seed in (("e1", 1), ("e2", 9999)):
        build_release(
            snapshot=snapshot,
            golden_records=goldens,
            quality_by_id=quality_by_id,
            config=ProductConfig(
                product_name="seeded",
                product_type="TRAIN",
                visibility="INTERNAL",
                split_policy=SplitPolicy(seed=seed),
            ),
            out_dir=tmp_path / out_name,
            factory_version="0.7.0",
            provenance_version="1.0",
        )
    diff = diff_releases(tmp_path / "e1", tmp_path / "e2")
    assert diff.config_changed is True
    assert diff.records_added or diff.records_removed or diff.splits_changed


def test_dataset_card_states_facts(tmp_path):
    built, _, _, snapshot = _build(tmp_path, name="c")
    card = (tmp_path / "c" / "dataset_card.md").read_text(encoding="utf-8")
    assert built.manifest.release_id in card
    assert snapshot.dataset_snapshot_id in card
    assert "DuckDB" in card


def _all_records(release_dir):
    from verified_data_factory.products import read_jsonl, read_manifest

    manifest = read_manifest(release_dir / "manifest.json")
    records = []
    for shard in manifest.shards:
        path = release_dir / shard.relative_path
        records.extend(read_jsonl(path) if path.suffix == ".jsonl" else _read_parquet(path))
    return records


def _read_parquet(path):
    from verified_data_factory.products import read_parquet

    return read_parquet(path)


def test_metrics_reference_split_counts(tmp_path):
    _build(tmp_path, name="mt")
    metrics = json.loads((tmp_path / "mt" / "metrics.json").read_text(encoding="utf-8"))
    assert (
        metrics["train_count"] + metrics["public_eval_count"] + metrics["private_eval_count"]
        == metrics["record_count"]
    )
