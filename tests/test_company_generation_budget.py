"""Interrupted calls consume budget; duplicate/invalid accounting cannot restore it."""
from copy import deepcopy

import httpx
import pytest

from scripts import company_generation_experiment as experiment
from scripts.company_generation_experiment import budget_usage, reserve


def test_interrupted_call_blocks_new_inference_and_retains_time_reservation():
    event = reserve([], "run:0")
    assert budget_usage([event]) == {"physical_attempts": 1, "generation_seconds": 180,
                                   "unfinished_attempts": ["run:0"]}
    with pytest.raises(ValueError, match="interrupted"):
        reserve([event], "run:1")
    finished = {"attempt_id": "run:0", "state": "finished", "elapsed_seconds": 7.5}
    assert budget_usage([event, finished])["generation_seconds"] == 7.5
    assert reserve([event, finished], "run:1")["reserved_seconds"] == 180
    with pytest.raises(ValueError, match="spent"):
        reserve([event, finished], "run:0")


def test_budget_caps_and_tamper_checks():
    events = []
    for index in range(360):
        events.extend([{"attempt_id": str(index), "state": "started", "reserved_seconds": 180},
                       {"attempt_id": str(index), "state": "finished", "elapsed_seconds": 1}])
    with pytest.raises(ValueError, match="exhausted"):
        reserve(events, "new-run:0")
    changed = deepcopy(events[:2])
    changed[1]["elapsed_seconds"] = -1
    with pytest.raises(ValueError, match="accounting"):
        budget_usage(changed)
    with pytest.raises(ValueError, match="duplicate"):
        budget_usage([events[0], events[0]])
    with pytest.raises(ValueError, match="exhausted"):
        reserve([events[0], {**events[1], "elapsed_seconds": 14400}], "next")


def test_transport_timeout_keeps_indeterminate_reservation_and_exact_public_prompt(tmp_path, monkeypatch):
    import json

    run = tmp_path / "test-only-run"
    (run / "attempt-000").mkdir(parents=True)
    monkeypatch.setattr(experiment, "BUDGET", tmp_path / "test-budget.jsonl")

    def transport(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": experiment.MODEL, "digest": experiment.MODEL_DIGEST}]})
        assert json.loads(request.content)["messages"][0]["content"] == "public task only\n/no_think"
        raise httpx.ReadTimeout("test-only timeout")

    from verified_data_factory.generation import GenerationConfig

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = experiment.RecordedQwen(client, run)
        from verified_data_factory.generation.errors import ProviderTimeoutError

        with pytest.raises(ProviderTimeoutError):
            provider.generate("public task only", GenerationConfig())
    events = [json.loads(line) for line in experiment.BUDGET.read_text().splitlines()]
    assert budget_usage(events)["unfinished_attempts"] == ["test-only-run:0"]
    assert (run / "attempt-000/indeterminate-call.json").is_file()


def test_native_cpu_transport_preserves_model_identity_and_measured_usage(tmp_path, monkeypatch):
    import json

    run = tmp_path / "test-only-cpu"
    (run / "attempt-000").mkdir(parents=True)
    monkeypatch.setattr(experiment, "BUDGET", tmp_path / "test-cpu-budget.jsonl")

    def transport(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": experiment.MODEL, "digest": experiment.MODEL_DIGEST}]})
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["options"]["num_gpu"] == 0 and body["think"] is False
        return httpx.Response(200, json={"model": experiment.MODEL, "message": {"content": "SELECT 1"},
                                       "done_reason": "stop", "prompt_eval_count": 7, "eval_count": 2})

    from verified_data_factory.generation import GenerationConfig

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        provider = experiment.RecordedQwen(client, run, cpu=True)
        result = provider.generate("public only", GenerationConfig(seed=1))
        assert result.raw_text == "SELECT 1" and result.model == experiment.MODEL
        assert result.token_usage.total_tokens == 9
        assert result.provider_metadata["actual_endpoint"] == "/api/chat"
        assert provider.endpoint_id() != experiment.RecordedQwen(client, run).endpoint_id()
    events = [json.loads(line) for line in experiment.BUDGET.read_text().splitlines()]
    assert events[0]["request_sha256"] and events[1]["response_sha256"]
    from types import SimpleNamespace

    candidate = SimpleNamespace(model=experiment.MODEL, raw_response="SELECT 1", candidate_sql="SELECT 1",
                                model_revision="ollama-manifest:"+experiment.MODEL_DIGEST)
    experiment.validate_attempt_binding(run, 0, candidate, events)
    candidate.candidate_sql = "SELECT 2"
    with pytest.raises(ValueError, match="substituted"):
        experiment.validate_attempt_binding(run, 0, candidate, events)
    candidate.candidate_sql = "SELECT 1"
    candidate.raw_response = "SELECT 2"
    with pytest.raises(ValueError, match="differs"):
        experiment.validate_attempt_binding(run, 0, candidate, events)
    legacy = deepcopy(events)
    legacy[0].pop("request_sha256")
    with pytest.raises(ValueError, match="legacy"):
        experiment.validate_attempt_binding(run, 0, candidate, legacy)
