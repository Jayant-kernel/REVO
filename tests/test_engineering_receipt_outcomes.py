"""Legacy forgery variants remain denied; v2 binding tests live in Stage 2 tests."""
import json

from tests.test_engineering_readiness import complete
from verified_data_factory.verification.readiness import qualify, sha256


def test_legacy_mutation_summary_without_witnesses_remains_denied(tmp_path):
    record = complete(tmp_path)
    path = tmp_path / "mutation.json"
    data = json.loads(path.read_text())
    data.pop("mutants", None)
    data.pop("required_rules", None)
    path.write_text(json.dumps(data))
    record["evidence"]["mutation"]["sha256"] = sha256(path)
    assert not qualify(tmp_path, record)["eligible"]


def test_legacy_syntax_label_does_not_rescue_summary_admission(tmp_path):
    record = complete(tmp_path)
    path = tmp_path / "mutation.json"
    data = json.loads(path.read_text())
    data["required_rules"] = ["year"]
    data["mutants"] = [{"classification": "SYNTAX_ERROR", "rule_ids": ["year"]}] * 3
    path.write_text(json.dumps(data))
    record["evidence"]["mutation"]["sha256"] = sha256(path)
    assert not qualify(tmp_path, record)["eligible"]


def test_legacy_empty_output_summary_does_not_rescue_admission(tmp_path):
    record = complete(tmp_path)
    path = tmp_path / "fixture_diversity.json"
    data = json.loads(path.read_text())
    data["expected_results"] = [[], [], [], []]
    path.write_text(json.dumps(data))
    record["evidence"]["fixture_diversity"]["sha256"] = sha256(path)
    assert not qualify(tmp_path, record)["eligible"]
