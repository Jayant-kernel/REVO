import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.product_fixtures import make_golden
from verified_data_factory.products.engineering import check_assets, check_source
from verified_data_factory.products.errors import ProductConfigError
from verified_data_factory.products.isolation import connected_groups
from verified_data_factory.products.models import ProductConfig, SplitPolicy
from verified_data_factory.products.release import build_release
from verified_data_factory.provenance import build_dataset_snapshot


def test_empty_engineering_exports_and_missing_assets_are_rejected(tmp_path):
    manifest = SimpleNamespace(files=[], shards=[], record_count=0)
    errors = check_assets(tmp_path, manifest, [])
    assert "empty engineering release" in errors
    assert "complete SHA256SUMS required" in errors


def test_qualification_cannot_be_replaced_by_bare_pass_flag(tmp_path):
    with pytest.raises(ProductConfigError, match="record missing"):
        check_source(make_golden(1, "aggregation"), {"engineering_ready": True}, tmp_path)


def test_snapshot_membership_is_complete_before_export(tmp_path):
    golden = make_golden(1, "aggregation")
    snapshot = build_dataset_snapshot([golden.candidate_id, "missing-member"], "scope", "1", "selection", "1")
    config = ProductConfig(product_name="engineering-test", product_type="TRAIN", acceptance_profile="ENGINEERING_STRICT",
        split_policy=SplitPolicy(group_by="engineering_group", train=1, public_eval=0, private_eval=0),
        engineering_evidence_root=str(tmp_path), engineering_role_registry=str(tmp_path / "roles.json"))
    with pytest.raises(ProductConfigError, match="not all supplied"):
        build_release(snapshot=snapshot, golden_records=[golden], quality_by_id={}, config=config,
                      out_dir=tmp_path / "release", factory_version="1", provenance_version="1")
    assert not (tmp_path / "release").exists()


def test_actual_qualified_row_builds_and_roundtrips_strict_export(tmp_path):
    from scripts.engineering_pipeline import execute_sql
    from tests.test_business_tasks import SAAS_V2_CHAINED_JOIN_SQL
    from verified_data_factory.products.acceptance import retain_replay_inputs
    from verified_data_factory.products.validation import validate_release
    from verified_data_factory.quality.export import build_golden_record_id
    from verified_data_factory.quality.models import GoldenRecord
    from verified_data_factory.task_engine import generate_task, load_builtin_registry
    from verified_data_factory.verification.readiness import authoritative_records

    root = Path(__file__).resolve().parents[1]
    record = next(r for r in authoritative_records(root) if r["family"] == "funnel")
    isolated_root = tmp_path / "evidence"
    retain_replay_inputs(root, isolated_root, {}, [record])
    task = generate_task(load_builtin_registry().get(record["contract_id"], record["contract_version"]), 1)
    result = execute_sql(task, SAAS_V2_CHAINED_JOIN_SQL, 1)
    assert result["verification"]["verdict"] == "PASS"
    task_payload = task.model_dump(mode="json")
    schema = [t.model_dump(mode="json") for t in task.schema_]
    rid = build_golden_record_id(task=task_payload, instruction=task.instruction, schema=schema,
                               candidate_solution=SAAS_V2_CHAINED_JOIN_SQL, record_schema_version="2.0")
    golden = GoldenRecord(record_id=rid, candidate_id=result["verification"]["candidate_id"], task=task_payload,
        instruction=task.instruction, schema_=schema, fixture=task.fixture_metadata.model_dump(mode="json"),
        candidate_solution=SAAS_V2_CHAINED_JOIN_SQL, verification=result["verification"], quality={"decision": "GOLDEN"})
    groups = connected_groups([golden])
    quality = {golden.candidate_id: {"engineering_record": record, "engineering_isolation_group": groups[golden.candidate_id],
               "role": "TRAIN", "contamination_flags": [], "verification": {"verification_strength": "STRONG",
               "mutation_applicable": 3, "mutation_status": "SCORED", "mutation_score": 1.0}}}
    snapshot = build_dataset_snapshot([golden.candidate_id], "strict-test", "1", "selection", "1")
    config = ProductConfig(product_name="engineering-test", product_type="TRAIN", acceptance_profile="ENGINEERING_STRICT",
        split_policy=SplitPolicy(group_by="engineering_group", train=1, public_eval=0, private_eval=0),
        engineering_evidence_root=str(isolated_root), engineering_role_registry=str(tmp_path / "roles.json"))
    release = build_release(snapshot=snapshot, golden_records=[golden], quality_by_id=quality, config=config,
                            out_dir=tmp_path / "release", factory_version="1", provenance_version="1")
    assert release.validation.status == "VALID"
    assert release.manifest.record_count == 1
    assert validate_release(release.release_dir, qualities_by_id={golden.record_id: quality[golden.candidate_id]}).status == "VALID"
    dependencies = release.release_dir / "engineering_dependencies.json"
    original_dependencies = dependencies.read_bytes()
    altered = json.loads(original_dependencies)
    altered["runtime_versions"]["duckdb"] = "INVALID-TEST-VERSION"
    dependencies.write_text(json.dumps(altered))
    records = [json.loads(line) for line in (release.release_dir / release.manifest.shards[0].relative_path).read_text().splitlines()]
    assert "engineering dependency version changed" in check_assets(release.release_dir, release.manifest, records)
    altered = json.loads(original_dependencies)
    altered["files"][next(iter(altered["files"]))] = "0" * 64
    dependencies.write_text(json.dumps(altered))
    assert "engineering dependency changed or invalid path" in check_assets(release.release_dir, release.manifest, records)
    dependencies.write_bytes(original_dependencies)
    # Updating all checksum metadata cannot replace accepted SQL content.
    from verified_data_factory.products.manifest import write_checksums, write_manifest
    from verified_data_factory.products.serializers import hash_file

    shard = release.release_dir / release.manifest.shards[0].relative_path
    original_shard = shard.read_bytes()
    original_manifest = (release.release_dir / "manifest.json").read_bytes()
    original_sums = (release.release_dir / "SHA256SUMS").read_bytes()
    changed = json.loads(shard.read_text().splitlines()[0])
    changed["sql"] = "SELECT 1"
    shard.write_text(json.dumps(changed) + "\n")
    size, checksum = hash_file(shard)
    forged = release.manifest.model_copy(update={
        "shards": [s.model_copy(update={"byte_size": size, "content_hash": checksum})
                   if s.relative_path == release.manifest.shards[0].relative_path else s for s in release.manifest.shards],
        "files": [f.model_copy(update={"byte_size": size, "content_hash": checksum})
                  if f.relative_path == release.manifest.shards[0].relative_path else f for f in release.manifest.files],
    })
    write_manifest(forged, release.release_dir / "manifest.json")
    write_checksums({f.relative_path: hash_file(release.release_dir / f.relative_path) for f in forged.files}
                    | {"manifest.json": hash_file(release.release_dir / "manifest.json")}, release.release_dir / "SHA256SUMS")
    tampered = validate_release(release.release_dir)
    assert tampered.status == "INVALID"
    assert any("acceptance record content differs" in error.detail for error in tampered.errors)
    shard.write_bytes(original_shard)
    (release.release_dir / "manifest.json").write_bytes(original_manifest)
    (release.release_dir / "SHA256SUMS").write_bytes(original_sums)
    relocated = tmp_path / "relocated"
    shutil.copytree(release.release_dir, relocated)
    isolated_root.rename(tmp_path / "original-evidence-unavailable")
    replay = subprocess.run([sys.executable, str(relocated / "validate_engineering.py")], cwd=tmp_path,
                            capture_output=True, text=True, check=False, timeout=600)
    assert replay.returncode == 0, replay.stdout + replay.stderr
    assert json.loads(replay.stdout)["status"] == "VALID"
    # A typed output mutation remains invalid even if it is still parseable JSON.
    shard = release.release_dir / release.manifest.shards[0].relative_path
    original = shard.read_bytes()
    payload = json.loads(shard.read_text().splitlines()[0])
    payload["template_version"] = True
    shard.write_text(json.dumps(payload) + "\n")
    assert validate_release(release.release_dir, qualities_by_id={golden.record_id: quality[golden.candidate_id]}).status == "INVALID"
    shard.write_bytes(original)
    (release.release_dir / "SHA256SUMS").unlink()
    assert validate_release(release.release_dir, qualities_by_id={golden.record_id: quality[golden.candidate_id]}).status == "INVALID"
