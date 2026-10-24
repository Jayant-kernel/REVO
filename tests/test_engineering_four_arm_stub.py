from scripts.engineering_four_arm_stub import run


def test_four_arms_reuse_failed_baselines_and_resume_without_new_calls(tmp_path):
    report = run(tmp_path)
    assert report["provider_calls"] == 18
    assert [r["arm"] for r in report["arms"]] == ["pinned-baseline", "pinned-feedback", "qwen-baseline", "qwen-feedback"]
    assert report["arms"][1]["rescues"] == report["arms"][3]["rescues"] == 3
    before = [(tmp_path / name / "provider-calls.jsonl").read_bytes() for name in ("pinned", "qwen")]
    repeated = run(tmp_path)
    assert repeated["provider_calls"] == 0
    assert repeated["cumulative_provider_calls"] == report["cumulative_provider_calls"] == 18
    assert all(arm["new_provider_calls"] == 0 for arm in repeated["arms"])
    assert repeated["arms"][1]["new_rescues"] == repeated["arms"][3]["new_rescues"] == 0
    assert repeated["arms"][1]["new_evaluation_attempts_model"] == repeated["arms"][3]["new_evaluation_attempts_model"] == 0
    assert before == [(tmp_path / name / "provider-calls.jsonl").read_bytes() for name in ("pinned", "qwen")]
