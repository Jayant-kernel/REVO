"""Publication transaction checks; synthetic receipts do not qualify a task."""
import json

import pytest

from scripts import engineering_qualification_authority as authority
from scripts.package_a_evidence import materialize
from verified_data_factory.verification.readiness import REQUIRED
from verified_data_factory.verification.receipt_models import ArtifactRef
from verified_data_factory.verification.receipt_validation import digest


@pytest.mark.parametrize("late_drift", [False, True])
def test_transaction_captures_once_after_replay_and_rejects_late_drift(tmp_path, monkeypatch, late_drift):
    evidence = tmp_path / "scratch/funnel_experiment/evidence"
    evidence.mkdir(parents=True)
    (evidence / "events.jsonl").write_text("")
    index = evidence / "index.json"
    index.write_text(json.dumps(materialize([])))
    (tmp_path / "manifests").mkdir()
    (tmp_path / "manifests/package-a-contract-quarantine.json").write_text(json.dumps({"version": 1, "quarantines": []}))
    source = tmp_path / "protected.py"
    source.write_text("original")
    sources = {source.name: digest(source)}
    references, replayed, captured = {}, [], []
    for category in REQUIRED:
        path = tmp_path / (category + ".json")
        path.write_text(json.dumps({"evidence_id": "synthetic-transaction-" + category,
                                    "producer": "test_fixture.py", "source_hashes": sources}))
        references[category] = {"path": path.name, "sha256": digest(path)}
    bundle = tmp_path / "bundle.json"
    bundle.write_text(json.dumps({"contract_id": "synthetic.transaction.only", "contract_version": 1,
                                 "evidence": references}))

    def replay(root, reference, contract, version, category):
        replayed.append(category)
        if late_drift and len(replayed) == len(REQUIRED):
            source.write_text("changed during validation")
        return json.loads((root / reference["path"]).read_text()), "fresh executed evidence"

    def capture(root):
        assert replayed == list(REQUIRED)
        captured.append(root)
        return {"scope": "synthetic transaction only"}

    monkeypatch.setattr(authority, "receipt", replay)
    monkeypatch.setattr(authority, "source_tree_identity", capture)
    ref = ArtifactRef(path=bundle.name, sha256=digest(bundle))
    if late_drift:
        with pytest.raises(ValueError, match="missing or stale artifact"):
            authority.promote(tmp_path, ref)
        assert (evidence / "events.jsonl").read_text() == ""
        assert json.loads(index.read_text()) == materialize([])
    else:
        event = authority.promote(tmp_path, ref)
        assert len(event["members"]) == 7
        assert all(member["source_tree_identity"] == capture_value for member in event["members"]
                   for capture_value in [{"scope": "synthetic transaction only"}])
    assert captured == [tmp_path]
