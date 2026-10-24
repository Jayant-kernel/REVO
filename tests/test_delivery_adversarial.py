"""Explicit public-semantic expectations plus unchanged original-model runtime proof."""
from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

from tests.verify_testkit import make_candidate
from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.quality.premium_candidate import assess_premium_candidate
from verified_data_factory.sandbox import load_config
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.task_engine.models import TaskInstance
from verified_data_factory.verification import VerificationConfig, get_oracle, verify_candidate
from verified_data_factory.verification.adversarial import independent_adversarial_tables
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.delivery_adversarial import delivery_adversarial
from verified_data_factory.verification.hidden import run_hidden_checks

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "sql.dedup.lowest_quote": [["", "", 0], ["axle", "Zulu", 430], ["ceiling", "Solo", 2147483647]],
    "sql.joins.requested_language_titles": [
        [71, "Mar"], [71, "Mar"], [71, None], [71, "Mar"], [71, "Mar"], [71, None],
        [72, None], [73, None], [74, None], [75, ""],
    ],
    "sql.subqueries.pareto_shipping": [
        [81, "dock", 40, 90], [82, "dock", 40, 90], [84, "dock", 70, 60],
        [86, "DOCK", 100, 100], [88, "", 0, 0],
    ],
    "sql.retention.renewal_coverage": [[91, True], [92, False], [93, False], [94, False], [95, True]],
    "sql.windows.queue_batches": [
        [110, 1], [111, 1], [112, 1], [113, 2], [114, 2], [115, 3], [116, 3],
        [117, 1], [118, 2], [119, 1],
    ],
}
# Executable business mistakes, authored here rather than taken from profile mutants.
WRONG_SQL = {
    "sql.dedup.lowest_quote": (
        "SELECT part,supplier,price_cents FROM quotes WHERE price_cents IS NOT NULL "
        "QUALIFY ROW_NUMBER() OVER(PARTITION BY part ORDER BY price_cents,supplier DESC)=1 "
        "ORDER BY part"
    ),
    "sql.joins.requested_language_titles": (
        "SELECT DISTINCT r.request_id,t.title FROM requests r LEFT JOIN translations t "
        "ON r.item_id=t.item_id AND r.language=t.language"
    ),
    "sql.subqueries.pareto_shipping": (
        "SELECT o.option_id,o.lane,o.cost_cents,o.duration_minutes FROM options o "
        "WHERE o.cost_cents IS NOT NULL AND o.duration_minutes IS NOT NULL AND NOT EXISTS "
        "(SELECT 1 FROM options b WHERE b.lane=o.lane AND b.cost_cents<o.cost_cents "
        "AND b.duration_minutes<o.duration_minutes) ORDER BY o.option_id"
    ),
    "sql.retention.renewal_coverage": (
        "SELECT e.episode_id,EXISTS(SELECT 1 FROM renewals r WHERE r.member_id=e.member_id "
        "AND r.status='confirmed' AND r.begins_at<=e.expires_at "
        "AND CAST(r.ends_at AS DATE)>=CAST(e.expires_at AS DATE)+14) AS covered "
        "FROM episodes e WHERE YEAR(e.expires_at)=2025 ORDER BY e.episode_id"
    ),
    "sql.windows.queue_batches": (
        "SELECT submission_id,NTILE(3) OVER(PARTITION BY queue ORDER BY "
        "submitted_at ASC NULLS FIRST,submission_id) AS batch_number "
        "FROM submissions ORDER BY submission_id"
    ),
}


def same_rows(contract, rows):
    if contract == "sql.joins.requested_language_titles":
        return Counter(map(tuple, rows)) == Counter(map(tuple, EXPECTED[contract]))
    return rows == EXPECTED[contract]


@pytest.mark.parametrize("contract", EXPECTED)
def test_explicit_expected_and_executable_business_error(contract):
    task = generate_task(load_builtin_registry().get(contract, 1), 94001)
    tables = delivery_adversarial(contract, 1)
    assert tables is not None
    expected = get_oracle(contract, 1).fn(task.requirements, tables)
    assert same_rows(contract, expected.rows)
    assert tables != task.tables
    # Provider calls cannot share mutable tables; unsupported versions never alias v1.
    other = delivery_adversarial(contract, 1)
    assert other == tables and other is not tables
    next(iter(other.values())).clear()
    assert delivery_adversarial(contract, 1) == tables
    for version in (0, 2, 99):
        assert delivery_adversarial(contract, version) is None
    for frame in (tables, {name: list(reversed(rows)) for name, rows in tables.items()}):
        connection = materialize_duckdb(task.schema_, frame)
        try:
            actual = [list(row) for row in connection.execute(WRONG_SQL[contract]).fetchall()]
            assert not same_rows(contract, actual)  # SQL errors propagate, never count as kills.
        finally:
            connection.close()


def test_unknown_contract_has_no_fixture():
    assert delivery_adversarial("sql.dedup.lowest_quote_typo", 1) is None


def originals(contract):
    inventory = json.loads((ROOT / "scratch/company_evaluation/record-delivery-v2/"
                            "consolidated-v35/inventory.json").read_text())
    row = next(row for row in inventory["rows"] if row["contract_id"] == contract)
    generation_path = ROOT / row["physical_bindings"][0]["generation"]
    run = generation_path.parent.parent
    protocol = json.loads((run / "protocol.json").read_text())
    task = TaskInstance.model_validate(next(t for t in protocol["tasks"] if t["task_id"] == row["task_id"]))
    candidate = CandidateSolution.model_validate(json.loads(generation_path.read_text())["candidate_solution"])
    packet = Path(row["durable_location"]) / "packet/membership.json"
    membership = json.loads(packet.read_text())
    golden = next(m["golden"] for m in membership["members"] if m["candidate_id"] == candidate.candidate_id)
    assert candidate.candidate_id == row["candidate_id"]
    assert candidate.task_id == task.task_id
    assert candidate.candidate_sql == golden["candidate_solution"]
    assert golden["record_id"] == row["golden_record_id"]
    protected = [generation_path, run / "protocol.json", packet]
    return task, candidate, golden, protected


@pytest.mark.parametrize("contract", EXPECTED)
def test_original_native_verifier_and_screen(contract, tmp_path):
    task, candidate, golden, protected = originals(contract)
    before = {str(p): sha256(p.read_bytes()).hexdigest() for p in protected}
    tables = delivery_adversarial(contract, 1)
    # Real shared dispatch and unmodified backend: no injected production provider.
    assert tables is not None
    assert independent_adversarial_tables(task) == tables
    backend = DerivedTaskBackend(load_config(ROOT / "configs/sandbox_production.yaml"))
    assert backend.independent_adversarial_tables(task) == tables
    execution = backend.run(task, candidate, None, "original")
    verification = verify_candidate(task, candidate, execution, backend=backend)
    (tmp_path / "execution.json").write_text(execution.model_dump_json(indent=2))
    (tmp_path / "verification.json").write_text(verification.model_dump_json(indent=2))
    fixture_execution = backend.run(task, candidate, tables, "explicit-fixture")
    (tmp_path / "fixture-execution.json").write_text(fixture_execution.model_dump_json(indent=2))
    assert fixture_execution.status == "SUCCEEDED", fixture_execution.model_dump_json()
    assert same_rows(contract, fixture_execution.result_data.rows)
    assert execution.status == "SUCCEEDED"
    assert verification.verdict == "PASS", verification.model_dump_json()
    assert verification.verification_strength == "STRONG"
    cases = [c for c in verification.hidden.cases if c.source == "INDEPENDENT_ADVERSARIAL"]
    assert len(cases) == 1 and cases[0].status == "PASS"
    wrong = make_candidate(task, WRONG_SQL[contract])
    wrong_execution = backend.run(task, wrong, tables, "wrong-fixture")
    (tmp_path / "wrong-execution.json").write_text(wrong_execution.model_dump_json(indent=2))
    assert wrong_execution.status == "SUCCEEDED", wrong_execution.model_dump_json()
    assert not same_rows(contract, wrong_execution.result_data.rows)
    hidden = run_hidden_checks(task, wrong, get_oracle(contract, 1).fn, backend, [],
                               VerificationConfig().comparison)
    (tmp_path / "wrong-hidden.json").write_text(hidden.model_dump_json(indent=2))
    independent = [c for c in hidden.cases if c.source == "INDEPENDENT_ADVERSARIAL"]
    assert len(independent) == 1 and independent[0].status == "FAIL"
    # Exercise real Golden serialization, preserving original SQL/task identity.
    from verified_data_factory.quality.export import golden_record_for
    from verified_data_factory.quality.models import RecordQuality, VerifiedRecord

    record = VerifiedRecord(task=task, candidate=candidate, execution=execution,
                            verification=verification, role="TRAIN")
    quality = RecordQuality.model_validate(golden["quality"])
    exported = golden_record_for(quality, record).model_dump(mode="json", by_alias=True)
    assert exported["candidate_solution"] == candidate.candidate_sql
    path = tmp_path / "golden.jsonl"
    path.write_text(json.dumps(exported) + "\n")
    screen = assess_premium_candidate(path)
    (tmp_path / "screen.json").write_text(json.dumps(screen, indent=2))
    assert screen["gates"]["automated_row_evidence"]["passed"], screen["row_failures"]
    # Other 80-row product gates remain intact and false for a one-row diagnostic.
    assert not screen["automated_pre_review_gates_pass"]
    for fault in ("missing", "failed", "derived", "requirement", "duplicate"):
        altered = deepcopy(exported)
        cases = altered["verification"]["hidden"]["cases"]
        targeted = next(c for c in cases if c["source"] == "INDEPENDENT_ADVERSARIAL")
        if fault == "missing":
            cases.remove(targeted)
        elif fault == "failed":
            targeted["status"] = "FAIL"
        elif fault == "duplicate":
            cases.append(deepcopy(targeted))
        else:
            targeted["source"] = "DERIVED" if fault == "derived" else "REQUIREMENT_COUNTEREXAMPLE"
        negative = tmp_path / f"negative-{fault}.jsonl"
        negative.write_text(json.dumps(altered) + "\n")
        report = assess_premium_candidate(negative)
        assert not report["gates"]["automated_row_evidence"]["passed"]
        assert any("independent adversarial runtime case" in r["reason"] for r in report["row_failures"])
        (tmp_path / f"negative-{fault}-screen.json").write_text(json.dumps(report, indent=2))
    assert {str(p): sha256(p.read_bytes()).hexdigest() for p in protected} == before
    (tmp_path / "identity.json").write_text(json.dumps({
        "candidate_id": candidate.candidate_id, "task_id": task.task_id,
        "candidate_sql": candidate.candidate_sql, "original_files_sha256": before,
        "routing": "real shared independent_adversarial_tables and DerivedTaskBackend; no mocks",
        "expected_rows": EXPECTED[contract], "tables": tables,
    }, indent=2))
    print(f"{contract}: {verification.verdict}/{verification.verification_strength}; "
          f"route=production/no mocks; independent=1 PASS; wrong=SUCCEEDED/semantic mismatch; "
          f"screen negatives=5; evidence={tmp_path}")
