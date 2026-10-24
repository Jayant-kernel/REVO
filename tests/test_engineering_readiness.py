"""Historical summary forgery reproducer; never a current positive baseline."""
import hashlib
import json

import pytest

from verified_data_factory.verification.readiness import REQUIRED, qualify, sha256


def complete(tmp_path):
    """Preserved legacy forgery inputs, not an actually complete v2 receipt."""
    source = tmp_path / "source.py"
    source.write_text("source")
    metrics = {
        "rules": {"declared_rules": 2, "covered_rules": 2},
        "named_tests": {"failed": 0, "passed": 2},
        "relations": {"executed": 2, "discriminating": 2, "failed": 0},
        "mutation": {"valid_non_equivalent": 3, "semantic_kills": 3, "rule_coverage": 1},
        "challenge": {"witnessed_wrong": 20, "qualified_correct": 3, "false_acceptances": 0, "false_rejections": 0},
        "fixture_diversity": {"distinct_contents": 4, "seed_cases": 3},
        "fuzz": {"valid_random_cases": 900, "observed_coverage_pass": True, "divergences": 0},
    }
    evidence = {}
    for category, values in metrics.items():
        path = tmp_path / (category + ".json")
        data = {"contract_id": "c", "contract_version": 2, "category": category,
                                    "evidence_id": category, "producer": "test", "created_at": "2026-10-07",
                                    "status": "ACTIVE", "execution_failures": 0, "checks_run": 1,
                                    "unresolved_findings": [], "source_hashes": {"source.py": sha256(source)},
                                    "test_nodes": ["test::positive"], "metrics": values}
        if category == "mutation":
            data["required_rules"] = ["year", "group", "amount"]
            data["mutants"] = [{"classification": "KILLED_WRONG_ANSWER", "execution_status": "SUCCEEDED",
                                "execution_id": f"test-exec-{i}", "sql": f"SELECT {i} AS v",
                                "sql_sha256": hashlib.sha256(f"SELECT {i} AS v".encode()).hexdigest(),
                                "fixture_sha256": "a" * 64, "rule_ids": [rule],
                                "expected": {"columns": ["v"], "column_types": ["INTEGER"], "rows": [[99]]},
                                "actual": {"columns": ["v"], "column_types": ["INTEGER"], "rows": [[i]]}}
                               for i, rule in enumerate(data["required_rules"])]
        if category == "fixture_diversity":
            data["expected_results"] = [[[1]], [[2]], [], [[3]]]
        path.write_text(json.dumps(data))
        evidence[category] = {"path": path.name, "sha256": sha256(path)}
    return {"contract_id": "c", "contract_version": 2, "independence": "differential verification",
            "prerequisites": {"template": True}, "evidence": evidence, "quarantine": None}


@pytest.mark.parametrize("category", REQUIRED)
def test_legacy_forgery_is_denied_with_or_without_each_category(tmp_path, category):
    record = complete(tmp_path)
    assert not qualify(tmp_path, record)["eligible"]
    assert any("unsupported legacy evidence" in reason for reason in qualify(tmp_path, record)["reasons"])
    del record["evidence"][category]
    record["status"] = "FULLY_VERIFIED"
    assert not qualify(tmp_path, record)["eligible"]


def test_legacy_forgery_remains_denied_after_dependency_edit(tmp_path):
    record = complete(tmp_path)
    (tmp_path / "source.py").write_text("changed")
    assert not qualify(tmp_path, record)["eligible"]


def test_legacy_forgery_remains_denied_after_version_edit(tmp_path):
    record = complete(tmp_path)
    record["contract_version"] = 3
    assert not qualify(tmp_path, record)["eligible"]


def test_independent_count_rejects_forged_summary(tmp_path):
    from scripts.engineering_readiness_count import count
    record = complete(tmp_path)
    record["status"] = "FULLY_VERIFIED"
    del record["evidence"]["fuzz"]
    path = tmp_path / "index.json"
    path.write_text(json.dumps({"contracts": [record]}))
    with pytest.raises(ValueError, match="differs from artifact"):
        count(tmp_path, path)


def test_legacy_forgery_remains_denied_after_caller_flags_and_failure_edit(tmp_path):
    record = complete(tmp_path)
    record["quarantine"] = {"reason": "open rule"}
    assert not qualify(tmp_path, record)["eligible"]
    record = complete(tmp_path)
    path = tmp_path / "mutation.json"
    data = json.loads(path.read_text())
    data["execution_failures"] = 1
    path.write_text(json.dumps(data))
    record["evidence"]["mutation"]["sha256"] = sha256(path)
    assert not qualify(tmp_path, record)["eligible"]
