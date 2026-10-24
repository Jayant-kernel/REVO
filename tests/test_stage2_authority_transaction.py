"""Transaction shape tests are not substitutes for executed qualification bundles."""
import json

import pytest

from scripts.engineering_qualification_authority import promote
from scripts.package_a_evidence import materialize
from verified_data_factory.local_lock import exclusive_lock
from verified_data_factory.verification.readiness import REQUIRED
from verified_data_factory.verification.receipt_models import ArtifactRef
from verified_data_factory.verification.receipt_validation import digest


def event(category):
    return {"evidence_id": "fixture-" + category, "event_type": "qualification_category",
            "artifact_path": category + ".json", "sha256": "0" * 64, "status": "ACTIVE",
            "supersedes": None, "superseded_by": None, "producer_script": "fixture.py",
            "producer_command": "test fixture", "source_tree_identity": {}, "created_at": "2026-10-08",
            "contract_id": "sql.aggregation.manufacturing_line_scrap", "contract_version": 1,
            "phase": "stage2", "notes": "structural unit fixture only", "category": category}


def test_materialized_bundle_is_complete_or_rejected():
    members = [event(category) for category in REQUIRED]
    commit = {**members[0], "event_type": "qualification_bundle_commit", "members": members}
    index = materialize([commit])
    assert index["event_count"] == 1
    assert len(index["entries"]) == 7
    for partial in (members[:-1], [members[0]] * 7):
        with pytest.raises(ValueError, match="incomplete qualification bundle"):
            materialize([{**commit, "members": partial}])
    changed = {**members[0], "contract_version": 999}
    with pytest.raises(ValueError, match="misbound"):
        materialize([{**commit, "members": [changed, *members[1:]]}])
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        materialize([commit, commit])


def test_incomplete_bundle_never_changes_authority(tmp_path):
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps({"contract_id": "sql.aggregation.manufacturing_line_scrap",
                               "contract_version": 1, "evidence": {}}))
    with pytest.raises(ValueError, match="incomplete qualification bundle"):
        promote(tmp_path, ArtifactRef(path="bundle.json", sha256=digest(path)))
    assert not (tmp_path / "scratch/funnel_experiment/evidence/events.jsonl").exists()


def test_concurrent_authority_writer_cannot_acquire_lock(tmp_path):
    path = tmp_path / "authority.lock"
    with exclusive_lock(path), pytest.raises(OSError), exclusive_lock(path):
        pytest.fail("second writer acquired an owned kernel lock")
    with exclusive_lock(path):
        pass
