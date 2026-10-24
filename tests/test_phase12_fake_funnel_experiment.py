from pathlib import Path

from scripts.phase12_fake_funnel_experiment import ARMS, certify, feedback_envelope, leak_scan, run


def test_phase12_fake_run_certifies_all_four_arms_and_resumes(tmp_path: Path) -> None:
    first = run(tmp_path)
    calls_before = (tmp_path / "calls.jsonl").read_text(encoding="utf-8")
    second = run(tmp_path)
    assert first["status"]["result"] == second["status"]["result"] == "PASS"
    assert first["arms"] == second["arms"]
    assert all(first["arms"][arm] > 0 for arm in ARMS)
    assert (tmp_path / "calls.jsonl").read_text(encoding="utf-8") == calls_before
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "status.json").exists()
    assert (tmp_path / "evidence.json").exists()
    assert (tmp_path / "checklist.json").exists()


def test_phase12_cap_is_recorded_and_certification_detects_missing_arms(tmp_path: Path) -> None:
    result = run(tmp_path, arm_cap_calls=0)
    assert result["status"]["result"] == "FAIL"
    assert "missing arm: pinned-baseline" in result["status"]["errors"]
    assert "arm_call_cap" in (tmp_path / "calls.jsonl").read_text(encoding="utf-8")


def test_phase12_feedback_boundary_rejects_forbidden_data() -> None:
    row = {"verdict": "RESULT_MISMATCH", "candidate_sql": "SELECT 1"}
    envelope = feedback_envelope(row)
    assert "oracle" not in envelope.lower()
    try:
        leak_scan("mutation evidence")
    except ValueError as error:
        assert "mutation" in str(error)
    else:
        raise AssertionError("expected leak scan to reject forbidden verifier data")


def test_phase12_certificate_rejects_non_fake_call(tmp_path: Path) -> None:
    ledger = tmp_path / "calls.jsonl"
    run(tmp_path)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write('{"kind":"call","arm":"pinned-baseline","contract_id":"x","candidate_index":0,"retry_index":0,"provider":"real","provider_network_calls":1}\n')
    evidence = certify(tmp_path)
    assert evidence["status"]["result"] == "FAIL"
    assert any("non-fake provider" in error for error in evidence["status"]["errors"])
