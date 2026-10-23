"""Phase 10 readiness authority is derived and independently countable."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from verified_data_factory.production import contract_readiness_from_manifest

ROOT = Path(__file__).resolve().parents[1]


def _module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase10_index_has_one_current_record_per_contract_version(tmp_path: Path) -> None:
    authority = _module("package_a_phase10_readiness", "scripts/package_a_phase10_readiness.py")
    index = authority.build_index(ROOT, "2026-10-05")

    keys = [(row["contract_id"], row["contract_version"]) for row in index["contracts"]]
    assert len(keys) == len(set(keys))
    assert index["qualification_scope"] == "legacy scheduler diagnostics; not current source-bound receipt admission"
    assert authority._counts(index) == {
        "contracts": 62,
        "fully_verified": 5,
        "quarantined": 52,
        "not_ready": 5,
        "funnels": 8,
        "fully_verified_funnels": 1,
    }
    inventory = next(row for row in index["contracts"] if row["contract_id"] == "sql.cte.inventory_net_flow")
    # The dispatcher repair changes legacy diagnostics, not receipt admission.
    assert inventory["contract_version"] == 2
    assert inventory["status"] == "FULLY_VERIFIED"
    from verified_data_factory.verification.readiness import authoritative_records, qualify

    record = next(row for row in authoritative_records(ROOT) if row["contract_id"] == inventory["contract_id"])
    # V36 renewal admitted inventory v2, so scheduler diagnostics and receipt
    # admission now agree (both FULLY_VERIFIED). The historical index assertions
    # above are unchanged; this cross-check tracks current admission truth.
    assert qualify(ROOT, record)["eligible"]
    saas = next(row for row in index["contracts"] if row["contract_id"] == "sql.funnel.saas_activation_payment")
    assert saas["readiness_checks"]["independent_oracle"]["status"] == "differential"


def test_phase10_independent_counter_validates_generated_matrix(tmp_path: Path) -> None:
    authority = _module("package_a_phase10_readiness", "scripts/package_a_phase10_readiness.py")
    counter = _module("package_a_phase10_count", "scripts/package_a_phase10_count.py")
    index = authority.build_index(ROOT, "2026-10-05")
    matrix = authority.build_matrix(index)
    index_path, matrix_path = tmp_path / "index.json", tmp_path / "matrix.json"
    index_path.write_text(json.dumps(index), encoding="utf-8")
    matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
    report = counter.count(index_path, matrix_path)

    assert report["status"] == "PASS"
    assert report["totals"] == authority._counts(index)


def test_phase10_manifest_preserves_differential_saas_verification_for_scheduler(tmp_path: Path) -> None:
    authority = _module("package_a_phase10_readiness", "scripts/package_a_phase10_readiness.py")
    index = authority.build_index(ROOT, "2026-10-05")
    manifest_path = tmp_path / "readiness.json"
    manifest_path.write_text(json.dumps(authority.build_manifest(index, None)), encoding="utf-8")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    saas = next(row for row in manifest["contracts"] if row["contract_id"] == "sql.funnel.saas_activation_payment")
    assert saas["independent_oracle"] == "differential"
    assert saas["status"] == "FULLY_VERIFIED"
    assert contract_readiness_from_manifest(manifest_path)("sql.funnel.saas_activation_payment")
