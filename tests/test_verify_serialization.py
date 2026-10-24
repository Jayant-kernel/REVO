"""Verification serialization tests: stable, bounded, secret-free."""

import json

from tests.verify_sql_samples import CORRECT_SQL
from tests.verify_testkit import SimBackend, make_candidate, make_execution, make_task, oracle_rows
from verified_data_factory.verification import (
    VerificationConfig,
    read_verifications_jsonl,
    verification_from_json,
    verification_to_json,
    verify_candidate,
    write_verifications_jsonl,
)


def _passing_result():
    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, CORRECT_SQL["sql.joins.simple"])
    columns, rows = oracle_rows(task)
    execution = make_execution(task, candidate, rows, columns)
    return verify_candidate(
        task, candidate, execution, VerificationConfig(mutation_enabled=False), SimBackend()
    )


def test_json_round_trip_stable():
    result = _passing_result()
    restored = verification_from_json(verification_to_json(result))
    assert restored.verdict == "PASS"
    assert restored.verification_id == result.verification_id
    assert restored.hidden == result.hidden
    assert restored.oracle == result.oracle


def test_jsonl_round_trip(tmp_path):
    path = write_verifications_jsonl([_passing_result(), _passing_result()], tmp_path / "v.jsonl")
    restored = read_verifications_jsonl(path)
    assert len(restored) == 2
    assert all(r.verdict == "PASS" for r in restored)


def test_evidence_bounded_on_mismatch():
    task = make_task("sql.joins.simple")
    candidate = make_candidate(task, CORRECT_SQL["sql.joins.simple"])
    columns, rows = oracle_rows(task)
    bad = [[r[0], 999999.0] for r in rows]  # every row differs
    execution = make_execution(task, candidate, bad, columns)
    result = verify_candidate(task, candidate, execution, VerificationConfig(), SimBackend())
    assert result.verdict == "FAIL"
    assert result.comparison is not None
    assert len(result.comparison.differences) <= 3
    blob = verification_to_json(result)
    assert len(blob.encode("utf-8")) < 100_000


def test_output_carries_versions_and_no_secrets_or_fixtures():
    result = _passing_result()
    data = json.loads(verification_to_json(result))
    assert data["verification_config_version"] == "1.4-candidate-public-rules"
    assert data["comparison"]["comparison_version"] == "3.0-authoritative"
    assert data["hidden"]["fixture_version"] == "2.0-content"
    assert data["hidden"]["distinct_fixtures"] == data["hidden"]["minimum_distinct_fixtures"] == 4
    assert all(len(case["fixture_sha256"]) == 64 for case in data["hidden"]["cases"])
    assert data["oracle_version"] == 2
    assert data["oracle"]["strategy"]
    blob = verification_to_json(result).lower()
    assert "api_key" not in blob and "bearer" not in blob
    # Fixture cell values must not leak (customer names are PII-like).
    task = make_task("sql.joins.simple")
    names = [r["name"] for r in task.tables["customers"][:3]]
    for name in names:
        assert name.lower() not in blob


def test_hidden_seeds_recorded_without_contents():
    result = _passing_result()
    assert result.hidden is not None
    assert len(result.hidden.seeds) == result.hidden.total == 3
    assert result.hidden.cases and all(c.seed in result.hidden.seeds for c in result.hidden.cases)
