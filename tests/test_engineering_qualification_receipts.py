import json
from pathlib import Path

from verified_data_factory.verification.readiness import qualify


def test_two_historical_profiles_preserve_generation_time_receipts_but_do_not_admit_now():
    root = Path(__file__).resolve().parents[1]
    path = root / "scratch/funnel_experiment/engineering/qualified-receipts-v2/index.json"
    records = json.loads(path.read_text())["contracts"]
    assert len(records) == 2
    # Later source edits legitimately invalidate admission. The immutable
    # generation-time index binds its initial qualifying results.
    assert all(r["eligible"] for r in records)
    for record in records:
        result = qualify(root, record)
        assert not result["eligible"]
        assert any("stale or unsupported legacy evidence" in reason for reason in result["reasons"])
        assert len(record["evidence"]) == 7


def test_survivor_findings_are_explicit_and_never_admit_a_contract():
    path = Path("scratch/funnel_experiment/engineering/phase7-survivors-r1.json")
    report = json.loads(path.read_text())
    assert len(report["campaigns"]) == 114
    assert report["survivor_count"] == len(report["survivors"])
    assert all(r["disposition"] in {"OPEN_COVERAGE_FINDING", "COUNTEREXAMPLE_WITNESSED"} and r["qualification_allowed"] is False for r in report["survivors"])
