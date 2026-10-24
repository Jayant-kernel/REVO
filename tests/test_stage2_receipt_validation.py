"""Receipt admission is fail-closed independently of caller summaries."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from verified_data_factory.verification.readiness import qualify, receipt, sha256
from verified_data_factory.verification.receipt_validation import required_sources, runtime_identity

CONTRACT = "sql.aggregation.manufacturing_line_scrap"


def quarantine_authority(root, entries=()):
    directory = root / "manifests"
    directory.mkdir(exist_ok=True)
    (directory / "package-a-contract-quarantine.json").write_text(
        json.dumps({"version": 1, "quarantines": list(entries)}), encoding="utf-8",
    )


def legacy_reference(root):
    path = root / "legacy.json"
    path.write_text(json.dumps({
        "contract_id": CONTRACT, "contract_version": 1, "category": "rules",
        "evidence_id": "forged", "producer": "test", "created_at": "2026-10-08",
        "status": "ACTIVE", "checks_run": 1, "execution_failures": 0,
        "unresolved_findings": [], "source_hashes": {"legacy.json": "irrelevant"},
        "metrics": {"declared_rules": 8, "covered_rules": 8},
    }), encoding="utf-8")
    return {"path": path.name, "sha256": sha256(path)}


def test_summary_only_receipt_is_explicitly_denied_as_legacy(tmp_path):
    _, reason = receipt(tmp_path, legacy_reference(tmp_path), CONTRACT, 1, "rules")
    assert reason == "stale or unsupported legacy evidence"


def test_unknown_public_contract_is_not_admitted(tmp_path):
    quarantine_authority(tmp_path)
    result = qualify(tmp_path, {"contract_id": "sql.invented", "contract_version": 1})
    assert not result["eligible"]
    assert "unknown public contract/version" in result["reasons"]


def test_caller_cannot_erase_versioned_authoritative_quarantine(tmp_path):
    quarantine_authority(tmp_path, [{
        "contract_id": CONTRACT, "contract_version": 1, "evidence_id": "open-proof",
        "reason": "unresolved behavior", "scope": ["production"],
    }])
    result = qualify(tmp_path, {
        "contract_id": CONTRACT, "contract_version": 1, "quarantine": None,
        "status": "FULLY_VERIFIED",
    })
    assert result["status"] == "QUARANTINED"
    assert "active authoritative quarantine" in result["reasons"]


@pytest.mark.parametrize("malformed", [None, {"version": 2, "quarantines": []}])
def test_missing_or_malformed_quarantine_authority_denies(tmp_path, malformed):
    if malformed is not None:
        quarantine_authority(tmp_path)
        (tmp_path / "manifests/package-a-contract-quarantine.json").write_text(
            json.dumps(malformed), encoding="utf-8",
        )
    result = qualify(tmp_path, {"contract_id": CONTRACT, "contract_version": 1})
    assert not result["eligible"]
    assert "missing or malformed quarantine authority" in result["reasons"]


def test_retained_real_contract_probe(record_property):
    """Executed separately to create the positive named-test XML, not synthesized."""
    from tests.verify_testkit import make_task
    from verified_data_factory.verification.oracle_registry import get_oracle

    record_property("node_id", "tests/test_stage2_receipt_validation.py::test_retained_real_contract_probe")
    record_property("contract_id", CONTRACT)
    record_property("contract_version", "1")
    task = make_task(CONTRACT, seed=94001)
    assert len(get_oracle(CONTRACT, 1).fn(task.requirements, task.tables).rows) == 3


def write_ref(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, default=str), encoding="utf-8")
    return {"path": name, "sha256": sha256(path)}


@pytest.fixture
def detailed_root(tmp_path):
    from tests.verify_testkit import make_task
    from verified_data_factory.task_engine.hidden_fixtures import (
        diverse_hidden_tables,
        fixture_fingerprint,
    )
    from verified_data_factory.verification.behavior_authority import public_behavior_map
    from verified_data_factory.verification.models import COMPARISON_VERSION
    from verified_data_factory.verification.oracle_registry import get_oracle

    live = Path(__file__).resolve().parents[1]
    sources = required_sources()
    producer = "tests/test_stage2_receipt_validation.py"
    sources[producer] = sha256(live / producer)
    for helper in ("tests/verify_testkit.py", "tests/verify_sql_samples.py"):
        sources[helper] = sha256(live / helper)
    for relative in sources:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(live / relative, destination)
    task = make_task(CONTRACT, seed=94001)
    oracle = get_oracle(CONTRACT, 1)
    task_ref = write_ref(tmp_path, "task.json", task.model_dump(mode="json", by_alias=True))
    base = {
        "schema_version": 2, "evidence_id": "isolated-executed-detail",
        "runtime": runtime_identity(),
        "producer": producer, "created_at": "2026-10-08T00:00:00+00:00",
        "contract_id": CONTRACT, "contract_version": 1, "task": task_ref,
        "oracle_version": oracle.oracle_version, "comparison_version": COMPARISON_VERSION,
        "behavior_map_sha256": public_behavior_map(task).declaration_sha256,
        "source_hashes": sources, "execution_failures": 0, "unresolved_findings": [],
    }
    fixtures = []
    for index, (origin, seed, tables) in enumerate([
        ("original", None, task.tables),
        *(("seed", seed, diverse_hidden_tables(task, seed, variant))
          for variant, seed in enumerate([1, 43, 94001], 1)),
    ]):
        fixtures.append({
            "origin": origin, "seed": seed,
            "tables": write_ref(tmp_path, f"tables-{index}.json", tables),
            "fingerprint": fixture_fingerprint(task, tables),
            "expected": oracle.fn(task.requirements, tables).model_dump(mode="json"),
        })
    return tmp_path, task, base, fixtures


def fixture_receipt(context):
    root, _, base, fixtures = context
    data = {**base, "category": "fixture_diversity", "checks_run": 4,
            "metrics": {"distinct_contents": 4, "seed_cases": 3},
            "details": {"fixtures": fixtures}}
    return write_ref(root, "fixture-receipt.json", data)


def test_real_fixture_details_validate_individually(detailed_root):
    root, _, _, _ = detailed_root
    valid, reason = receipt(root, fixture_receipt(detailed_root), CONTRACT, 1, "fixture_diversity")
    assert valid is not None, reason
    assert reason == "fresh executed evidence"


@pytest.mark.parametrize("defect, expected_reason", [
    ("summary", "summary counts differ"),
    ("fingerprint", "fixture fingerprint mismatch"),
    ("expected", "fixture expected result differs"),
    ("oracle", "stale oracle/comparison identifier"),
    ("comparison", "stale oracle/comparison identifier"),
    ("source", "missing or stale core source dependency"),
])
def test_detailed_fixture_tampering_reaches_intended_check(detailed_root, defect, expected_reason):
    root, _, _, _ = detailed_root
    reference = fixture_receipt(detailed_root)
    path = root / reference["path"]
    data = json.loads(path.read_text())
    if defect == "summary":
        data["checks_run"] = 99
    elif defect == "fingerprint":
        data["details"]["fixtures"][0]["fingerprint"] = "0" * 64
    elif defect == "expected":
        data["details"]["fixtures"][0]["expected"]["rows"] = []
    elif defect == "oracle":
        data["oracle_version"] += 1
    elif defect == "comparison":
        data["comparison_version"] = "invented"
    else:
        data["source_hashes"].pop("src/verified_data_factory/verification/comparator.py")
    reference = write_ref(root, reference["path"], data)
    valid, reason = receipt(root, reference, CONTRACT, 1, "fixture_diversity")
    assert valid is None
    assert expected_reason in reason


def named_receipt(context):
    root, _, base, _ = context
    live = Path(__file__).resolve().parents[1]
    node = "tests/test_stage2_receipt_validation.py::test_retained_real_contract_probe"
    command = [sys.executable, "-m", "pytest", node, "-q", "--junitxml", str(root / "named.xml")]
    result = subprocess.run(command, cwd=live, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    data = {**base, "category": "named_tests", "checks_run": 1,
            "metrics": {"passed": 1, "failed": 0}, "details": {
                "report": {"path": "named.xml", "sha256": sha256(root / "named.xml")},
                "nodes": {node: "passed"}, "command": command, "exit_code": result.returncode,
            }}
    return write_ref(root, "named-receipt.json", data)


def test_actual_named_xml_validates_individually(detailed_root):
    root, _, _, _ = detailed_root
    valid, reason = receipt(root, named_receipt(detailed_root), CONTRACT, 1, "named_tests")
    assert valid is not None, reason


def test_missing_named_report_cannot_pass_by_hash_label(detailed_root):
    root, _, _, _ = detailed_root
    reference = named_receipt(detailed_root)
    (root / "named.xml").unlink()
    valid, reason = receipt(root, reference, CONTRACT, 1, "named_tests")
    assert valid is None
    assert reason == "missing or stale artifact"


def test_new_schema_summary_only_cannot_pass(detailed_root):
    root, _, base, _ = detailed_root
    reference = write_ref(root, "forged-v2.json", {
        **base, "category": "rules", "checks_run": 8,
        "metrics": {"declared_rules": 8, "covered_rules": 8}, "details": {},
    })
    valid, reason = receipt(root, reference, CONTRACT, 1, "rules")
    assert valid is None
    assert reason == "missing or malformed detailed evidence"


CORRECT_SQL = (
    "SELECT group_key, SUM(amount) AS total_amount FROM production_runs "
    "WHERE status='eligible' AND EXTRACT(YEAR FROM occurred_at)=2025 "
    "GROUP BY group_key ORDER BY group_key ASC"
)


def retained_sql(context, sql, name, fixture_index=0):
    """Run real local DuckDB SQL and retain the actual typed execution, not an ID stub."""
    from datetime import UTC, datetime

    import duckdb

    from tests.verify_testkit import make_candidate
    from verified_data_factory.sandbox.executor import build_execution_id
    from verified_data_factory.sandbox.models import ExecutionResult
    from verified_data_factory.task_engine.fixtures import materialize_duckdb
    from verified_data_factory.verification.comparator import compare
    from verified_data_factory.verification.models import ExpectedResult

    root, task, _, fixtures = context
    fixture = fixtures[fixture_index]
    tables = json.loads((root / fixture["tables"]["path"]).read_text())
    candidate = make_candidate(task, sql)
    started = datetime.now(UTC).isoformat()
    connection = materialize_duckdb(task.schema_, tables)
    try:
        cursor = connection.execute(sql)
        columns = [{"name": c[0], "type": str(c[1])} for c in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
    finally:
        connection.close()
    finished = datetime.now(UTC).isoformat()
    duration = int((datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds() * 1000)
    output_bytes = len(json.dumps({"columns": len(columns), "rows": rows}, default=str).encode("utf-8"))
    execution = ExecutionResult.model_validate({
        "execution_id": build_execution_id(candidate.candidate_id, started),
        "task_id": task.task_id, "candidate_id": candidate.candidate_id,
        "status": "SUCCEEDED", "exit_code": 0, "duration_ms": duration,
        "result_data": {"columns": columns, "rows": rows, "rows_returned": len(rows)},
        "resource_limits": {"timeout_seconds": 5, "memory_mb": 128, "cpus": 1,
                            "pids_limit": 1, "max_result_rows": 100000,
                            "max_result_bytes": 10000000, "max_stdout_bytes": 0,
                            "max_stderr_bytes": 0},
        "resource_usage": {"duration_ms": duration, "output_bytes": output_bytes},
        "sandbox_image": "local-audit-duckdb",
        "sandbox_config_version": "local-audit-v1", "duckdb_version": duckdb.__version__,
        "started_at": started, "finished_at": finished,
    })
    expected = ExpectedResult.model_validate(fixture["expected"])
    comparison = compare(expected, [c["name"] for c in columns], rows,
                         column_types=[c["type"] for c in columns])
    path = root / f"{name}.sql"
    path.write_text(sql, encoding="utf-8")
    return {
        "sql": {"path": path.name, "sha256": sha256(path)},
        "candidate": write_ref(root, f"{name}-candidate.json", candidate.model_dump(mode="json")),
        "execution": write_ref(root, f"{name}-execution.json", execution.model_dump(mode="json")),
        "fixture": fixture, "comparison": comparison.model_dump(mode="json"),
        "outcome": "MATCH" if comparison.match else "KILLED_WRONG_ANSWER",
    }


def validator(context):
    from verified_data_factory.verification.behavior_authority import public_behavior_map
    from verified_data_factory.verification.receipt_validation import DetailValidator

    root, task, base, _ = context
    thresholds = json.loads((root / "configs/package_a/engineering-rubric.json").read_text())["thresholds"]
    return DetailValidator(root, task, public_behavior_map(task), base["source_hashes"], thresholds)


def test_real_executed_sql_witness_validates_individually(detailed_root):
    from verified_data_factory.verification.receipt_models import SQLWitness

    witness = retained_sql(detailed_root, CORRECT_SQL, "correct")
    assert witness["outcome"] == "MATCH"
    check = validator(detailed_root)
    check.sql(SQLWitness.model_validate(witness))
    assert check.run_count == 1
    check.sql(SQLWitness.model_validate(witness))
    assert check.run_count == 1  # references to the same execution do not invent extra runs


@pytest.mark.parametrize("defect, expected_reason", [
    ("execution_id", "inconsistent retained execution"),
    ("row_count", "execution detail consistency mismatch"),
    ("actual", "retained output differs from actual SQL replay"),
    ("comparison", "retained comparison differs from recomputation"),
    ("invalid_sql", "SQL replay failed"),
])
def test_sql_detail_tampering_hits_intended_binding_check(detailed_root, defect, expected_reason):
    from verified_data_factory.verification.receipt_models import SQLWitness

    root, _, _, _ = detailed_root
    witness = retained_sql(detailed_root, CORRECT_SQL, "correct")
    if defect == "comparison":
        witness["comparison"]["match"] = False
    elif defect == "invalid_sql":
        invalid = "SELECT missing_column FROM production_runs"
        (root / "correct.sql").write_text(invalid, encoding="utf-8")
        witness["sql"]["sha256"] = sha256(root / "correct.sql")
        candidate = json.loads((root / witness["candidate"]["path"]).read_text())
        candidate["candidate_sql"] = invalid
        witness["candidate"] = write_ref(root, witness["candidate"]["path"], candidate)
    else:
        execution = json.loads((root / witness["execution"]["path"]).read_text())
        if defect == "execution_id":
            execution["execution_id"] = "invented-label"
        elif defect == "row_count":
            execution["result_data"]["rows_returned"] = 999
        else:
            execution["result_data"]["rows"][0][1] += 1
        witness["execution"] = write_ref(root, witness["execution"]["path"], execution)
    with pytest.raises(ValueError, match=expected_reason):
        validator(detailed_root).sql(SQLWitness.model_validate(witness))


def test_mutation_rule_subset_rejected_against_public_ledger(detailed_root):
    from verified_data_factory.verification.receipt_models import MutationDetail

    correct = retained_sql(detailed_root, CORRECT_SQL, "correct")
    wrong = [retained_sql(detailed_root, CORRECT_SQL.replace("SUM(amount)", expression), f"wrong-{i}")
             for i, expression in enumerate(["SUM(amount)+1", "SUM(amount)+2", "SUM(amount)+3"])]
    detail = MutationDetail.model_validate({
        "required_rules": ["year"],
        "mutants": [{"rule_ids": ["year"], "correct": correct, "wrong": w} for w in wrong],
    })
    with pytest.raises(ValueError, match="required mutation rules differ from public authority"):
        validator(detailed_root).mutations(detail)


def test_caller_cannot_invent_quarantine_status(tmp_path):
    quarantine_authority(tmp_path)
    result = qualify(tmp_path, {"contract_id": CONTRACT, "contract_version": 1,
                                "quarantine": {"reason": "invented"}, "status": "QUARANTINED"})
    assert result["status"] == "NOT_READY"
    assert "active authoritative quarantine" not in result["reasons"]


def test_quarantine_is_exact_version_not_contract_wide(tmp_path):
    quarantine_authority(tmp_path, [{
        "contract_id": CONTRACT, "contract_version": 2, "evidence_id": "other-version",
        "reason": "different version", "scope": ["production"],
    }])
    result = qualify(tmp_path, {"contract_id": CONTRACT, "contract_version": 1})
    assert result["status"] == "NOT_READY"
    assert "active authoritative quarantine" not in result["reasons"]


def challenge_receipt(context):
    root, _, base, _ = context
    wrong = [retained_sql(context, CORRECT_SQL.replace("SUM(amount)", f"SUM(amount)+{i}"), f"challenge-{i}")
             for i in range(1, 21)]
    alternatives = [
        CORRECT_SQL,
        ("WITH scoped AS (SELECT * FROM production_runs WHERE status='eligible' "
        "AND EXTRACT(YEAR FROM occurred_at)=2025) SELECT group_key, SUM(amount) "
        "AS total_amount FROM scoped GROUP BY group_key ORDER BY group_key ASC"),
        ("SELECT group_key, SUM(amount) AS total_amount FROM production_runs WHERE "
        "occurred_at >= TIMESTAMP '2025-01-01' AND occurred_at < TIMESTAMP '2026-01-01' "
        "AND status='eligible' GROUP BY group_key ORDER BY group_key ASC"),
    ]
    correct = [retained_sql(context, sql, f"alternative-{i}") for i, sql in enumerate(alternatives)]
    return write_ref(root, "challenge-receipt.json", {
        **base, "category": "challenge", "checks_run": 23,
        "metrics": {"witnessed_wrong": 20, "qualified_correct": 3,
                    "false_acceptances": 0, "false_rejections": 0},
        "details": {"wrong": wrong, "correct": correct},
    })


def test_actual_challenge_details_validate_individually(detailed_root):
    root, _, _, _ = detailed_root
    valid, reason = receipt(root, challenge_receipt(detailed_root), CONTRACT, 1, "challenge")
    assert valid is not None, reason


def test_duplicate_challenge_does_not_invent_twentieth_wrong_query(detailed_root):
    root, _, _, _ = detailed_root
    reference = challenge_receipt(detailed_root)
    data = json.loads((root / reference["path"]).read_text())
    data["details"]["wrong"][-1] = data["details"]["wrong"][0]
    valid, reason = receipt(root, write_ref(root, reference["path"], data), CONTRACT, 1, "challenge")
    assert valid is None
    assert reason == "challenge outcomes or distinct alternatives incomplete"


def add_targeted_fixture(context, tables, name):
    from verified_data_factory.task_engine.hidden_fixtures import fixture_fingerprint
    from verified_data_factory.verification.oracle_registry import get_oracle

    root, task, _, fixtures = context
    fixtures.append({"origin": "targeted", "seed": None,
                     "tables": write_ref(root, name, tables),
                     "fingerprint": fixture_fingerprint(task, tables),
                     "expected": get_oracle(CONTRACT, 1).fn(task.requirements, tables).model_dump(mode="json")})
    return len(fixtures) - 1


def relation_receipt(context):
    from verified_data_factory.verification.metamorphic import contract_relation_tables

    root, task, base, _ = context
    sample = dict(next(row for row in task.tables["production_runs"]
                       if row["status"] == "eligible" and row["occurred_at"].startswith("2025")))
    sample["amount"] = 3
    tables = {"production_runs": [sample]}
    before_index = add_targeted_fixture(context, tables, "relation-before.json")
    relations = []
    for index, relation in enumerate(["SCRAP_ADDITIVITY", "SCRAP_EXCLUDED_ROW"]):
        transformed, precondition = contract_relation_tables(task, tables, relation)
        assert transformed is not None
        after_index = add_targeted_fixture(context, transformed, f"relation-after-{index}.json")
        wrong_sql = (CORRECT_SQL.replace("SUM(amount)", "MAX(amount)") if index == 0
                     else CORRECT_SQL.replace("status='eligible'", "TRUE"))
        relations.append({
            "relation_id": relation, "relation_version": 2, "precondition": precondition,
            "correct_before": retained_sql(context, CORRECT_SQL, f"r{index}-correct-before", before_index),
            "correct_after": retained_sql(context, CORRECT_SQL, f"r{index}-correct-after", after_index),
            "wrong_before": retained_sql(context, wrong_sql, f"r{index}-wrong-before", before_index),
            "wrong_after": retained_sql(context, wrong_sql, f"r{index}-wrong-after", after_index),
        })
    return write_ref(root, "relation-receipt.json", {
        **base, "category": "relations", "checks_run": 8,
        "metrics": {"executed": 2, "discriminating": 2, "failed": 0},
        "details": {"relations": relations},
    })


def test_two_real_identified_relation_transforms_validate_individually(detailed_root):
    root, _, _, _ = detailed_root
    valid, reason = receipt(root, relation_receipt(detailed_root), CONTRACT, 1, "relations")
    assert valid is not None, reason


def test_relation_tampered_precondition_is_not_admitted(detailed_root):
    root, _, _, _ = detailed_root
    reference = relation_receipt(detailed_root)
    data = json.loads((root / reference["path"]).read_text())
    data["details"]["relations"][0]["precondition"] = "invented precondition"
    valid, reason = receipt(root, write_ref(root, reference["path"], data), CONTRACT, 1, "relations")
    assert valid is None
    assert reason == "relation precondition/transform mismatch"


def journal_record(root):
    """Journal-binding shells only, explicitly not passing category receipts."""
    from scripts.package_a_evidence import materialize
    from verified_data_factory.verification.readiness import REQUIRED

    events = []
    evidence = {}
    for category in REQUIRED:
        evidence_id = f"journal-shell-{category}"
        reference = write_ref(root, f"journal-{category}.json", {
            "evidence_id": evidence_id, "producer": "tests/test_stage2_receipt_validation.py",
        })
        evidence[category] = reference
        events.append({
            "evidence_id": evidence_id, "category": category,
            "event_type": "category_receipt", "artifact_path": reference["path"],
            "sha256": reference["sha256"], "status": "ACTIVE", "supersedes": None,
            "superseded_by": None, "producer_script": "tests/test_stage2_receipt_validation.py",
            "producer_command": "pytest journal-binding-only", "source_tree_identity": {},
            "created_at": "2026-10-08T00:00:00+00:00", "contract_id": CONTRACT,
            "contract_version": 1, "phase": "stage2", "notes": "not category qualification",
        })
    directory = root / "scratch/funnel_experiment/evidence"
    directory.mkdir(parents=True)
    (directory / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    (directory / "index.json").write_text(json.dumps(materialize(events)))
    return {"contract_id": CONTRACT, "contract_version": 1, "evidence": evidence}, events


def test_effective_journal_bindings_validate_but_shells_never_qualify(tmp_path):
    from verified_data_factory.verification.readiness import effective_evidence

    record, _ = journal_record(tmp_path)
    quarantine_authority(tmp_path)
    effective_evidence(tmp_path, record)
    assert not qualify(tmp_path, record)["eligible"]


@pytest.mark.parametrize("defect", ["index", "superseded", "contract", "category"])
def test_effective_journal_rejects_status_and_binding_forgeries(tmp_path, defect):
    from scripts.package_a_evidence import materialize
    from verified_data_factory.verification.readiness import effective_evidence

    record, events = journal_record(tmp_path)
    directory = tmp_path / "scratch/funnel_experiment/evidence"
    if defect == "index":
        index = json.loads((directory / "index.json").read_text())
        index["entries"][0]["status"] = "SUPERSEDED"
        (directory / "index.json").write_text(json.dumps(index))
    else:
        if defect == "superseded":
            events.append({**events[0], "evidence_id": "supersession-event", "status": "INFORMATIONAL",
                           "supersedes": events[0]["evidence_id"]})
        elif defect == "contract":
            events[0]["contract_version"] = 2
        else:
            events[0]["category"] = "challenge"
        (directory / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
        (directory / "index.json").write_text(json.dumps(materialize(events)))
    with pytest.raises(ValueError):
        effective_evidence(tmp_path, record)


def test_independent_counter_uses_authoritative_quarantine(tmp_path):
    from scripts.engineering_readiness_count import count

    quarantine_authority(tmp_path, [{
        "contract_id": CONTRACT, "contract_version": 1, "evidence_id": "real-authority",
        "reason": "open evidence", "scope": ["production"],
    }])
    record = {"contract_id": CONTRACT, "contract_version": 1,
              "quarantine": None, "status": "QUARANTINED"}
    write_ref(tmp_path, "count.json", {"contracts": [record]})
    result = count(tmp_path, tmp_path / "count.json")
    assert result["totals"] == {"FULLY_VERIFIED": 0, "QUARANTINED": 1, "NOT_READY": 0}


def observed_inventory():
    """Actual 900 classified fixtures; metadata subvalidator only, not executed fuzz admission."""
    from collections import Counter

    from verified_data_factory.verification.receipt_models import FuzzObservation
    from verified_data_factory.verification.receipt_observations import (
        observation_fixture,
        observed_behaviors,
    )

    cases = []
    counts = {}
    for seed in [1, 43, 94001]:
        counter = None
        for index in range(300):
            tables = observation_fixture(CONTRACT, 1, seed, index)
            _, required, behaviors = observed_behaviors(CONTRACT, 1, tables)
            if counter is None:
                counter = Counter(dict.fromkeys(required, 0))
            counter.update(behaviors)
            cases.append(FuzzObservation(seed=seed, index=index, observed_behaviors=sorted(behaviors)))
        counts[str(seed)] = dict(counter)
    return cases, counts


def test_actual_observation_inventory_arithmetic_subvalidator(detailed_root):
    cases, counts = observed_inventory()
    assert len(cases) == 900
    assert validator(detailed_root).observation_inventory(cases, counts) == counts


def test_fake_observed_counts_rejected_from_real_classified_inventory(detailed_root):
    cases, counts = observed_inventory()
    counts["1"]["negative_amounts"] += 1
    with pytest.raises(ValueError, match="fuzz seed/case counts or observed summaries mismatch"):
        validator(detailed_root).observation_inventory(cases, counts)


@pytest.mark.parametrize("contract, version", [(CONTRACT, 1), ("sql.funnel.saas_activation_payment", 2)])
def test_receipt_observation_recipes_match_existing_profile_helpers(contract, version):
    from scripts.engineering_fuzz import classify, generate
    from scripts.engineering_scrap_coverage import generate as generate_scrap
    from scripts.engineering_scrap_coverage import observe
    from verified_data_factory.verification.receipt_observations import (
        observation_fixture,
        observed_behaviors,
    )

    generator, classifier = (generate_scrap, observe) if contract == CONTRACT else (generate, classify)
    for seed in [1, 43, 94001]:
        for index in [0, 1, 299]:
            tables = observation_fixture(contract, version, seed, index)
            assert tables == generator(seed, index)
            assert observed_behaviors(contract, version, tables)[2] == classifier(tables)


def test_named_report_subset_cannot_discard_actual_attributed_node(detailed_root):
    root, _, _, _ = detailed_root
    reference = named_receipt(detailed_root)
    data = json.loads((root / reference["path"]).read_text())
    data["details"]["nodes"] = {}
    valid, reason = receipt(root, write_ref(root, reference["path"], data), CONTRACT, 1, "named_tests")
    assert valid is None
    assert reason == "named test report outcomes/counts mismatch or nonpassing"


def test_consumed_producer_source_tampering_invalidates_details(detailed_root):
    root, _, base, _ = detailed_root
    reference = fixture_receipt(detailed_root)
    producer = root / base["producer"]
    producer.write_text(producer.read_text() + "\n# changed producer input\n")
    valid, reason = receipt(root, reference, CONTRACT, 1, "fixture_diversity")
    assert valid is None
    assert reason == "missing or stale artifact"


def test_unknown_receipt_contract_version_rejected_before_detail_admission(detailed_root):
    root, _, _, _ = detailed_root
    valid, reason = receipt(root, fixture_receipt(detailed_root), CONTRACT, 999, "fixture_diversity")
    assert valid is None
    assert reason == "unknown public contract/version"


def blocked_rule_detail(context):
    from verified_data_factory.verification.behavior_authority import public_behavior_map

    _, task, _, _ = context
    return {"rules": [{"rule_id": r.rule_id, "kind": r.kind,
                       "declaration_json": r.declaration_json, "disposition": "BLOCKED",
                       "blocked_reason": "no complete declared-behavior proof exists"}
                      for r in public_behavior_map(task).rules]}


def test_partial_rule_obligations_remain_explicitly_blocked(detailed_root):
    root, _, base, _ = detailed_root
    detail = blocked_rule_detail(detailed_root)
    reference = write_ref(root, "blocked-rules.json", {
        **base, "category": "rules", "checks_run": 1,
        "metrics": {"declared_rules": len(detail["rules"]), "covered_rules": 0},
        "details": detail,
    })
    valid, reason = receipt(root, reference, CONTRACT, 1, "rules")
    assert valid is None
    assert reason.startswith("blocked public behavior obligation:")


def test_public_semantic_rule_cannot_be_relabelled_as_domain_waiver(detailed_root):
    from verified_data_factory.verification.receipt_models import RulesDetail

    detail = blocked_rule_detail(detailed_root)
    year = next(r for r in detail["rules"] if r["rule_id"] == "year")
    detail["rules"].remove(year)
    year["kind"] = "input_domain"
    detail["rules"].insert(0, year)
    with pytest.raises(ValueError, match="invented rule declaration or domain waiver"):
        validator(detailed_root).rules(RulesDetail.model_validate(detail))


def test_caller_cannot_replace_original_seed_fixture_inside_base_task(detailed_root):
    root, _, _, _ = detailed_root
    reference = fixture_receipt(detailed_root)
    data = json.loads((root / reference["path"]).read_text())
    task = json.loads((root / data["task"]["path"]).read_text())
    task["tables"]["production_runs"][0]["amount"] += 1
    data["task"] = write_ref(root, "altered-base-task.json", task)
    valid, reason = receipt(root, write_ref(root, reference["path"], data), CONTRACT, 1, "fixture_diversity")
    assert valid is None
    assert reason == "retained base task differs from canonical generation inputs"


def test_noncanonical_timestamp_cannot_turn_correct_sql_into_a_semantic_kill(detailed_root):
    from verified_data_factory.verification.receipt_models import SQLWitness

    _, task, _, _ = detailed_root
    sample = {**task.tables["production_runs"][0], "group_key": "g", "status": "eligible",
              "amount": 3, "occurred_at": " 2025-01-01 00:00:00"}
    index = add_targeted_fixture(detailed_root, {"production_runs": [sample]}, "spaced-time.json")
    witness = retained_sql(detailed_root, CORRECT_SQL, "spaced-time", index)
    # Old raw-JSON oracle disagrees with the exact same typed database contents.
    assert witness["outcome"] == "KILLED_WRONG_ANSWER"
    with pytest.raises(ValueError, match="fixture expected result differs from current oracle"):
        validator(detailed_root).sql(SQLWitness.model_validate(witness))


@pytest.mark.parametrize("raw_changes, typed_changes", [
    ({"occurred_at": " 2025-01-01 00:00:00"}, {"occurred_at": "2025-01-01 00:00:00"}),
    ({"group_key": 123}, {"group_key": "123"}),
    ({"amount": 3.9}, {"amount": 4}),
])
def test_correct_sql_with_equivalent_typed_binding_remains_match(detailed_root, raw_changes, typed_changes):
    from verified_data_factory.verification.comparator import compare
    from verified_data_factory.verification.models import ExpectedResult
    from verified_data_factory.verification.oracle_registry import get_oracle
    from verified_data_factory.verification.receipt_models import SQLWitness

    root, task, _, _ = detailed_root
    sample = {**task.tables["production_runs"][0], "group_key": "g", "status": "eligible",
              "amount": 3, "occurred_at": "2025-01-01 00:00:00", **raw_changes}
    index = add_targeted_fixture(detailed_root, {"production_runs": [sample]}, "equivalent-time.json")
    witness = retained_sql(detailed_root, CORRECT_SQL, "equivalent-time", index)
    canonical = {"production_runs": [{**sample, **typed_changes}]}
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, canonical)
    assert expected.rows == [[canonical["production_runs"][0]["group_key"], canonical["production_runs"][0]["amount"]]]
    witness["fixture"]["expected"] = expected.model_dump(mode="json")
    actual = json.loads((root / witness["execution"]["path"]).read_text())["result_data"]
    witness["comparison"] = compare(ExpectedResult.model_validate(witness["fixture"]["expected"]),
                                    [c["name"] for c in actual["columns"]], actual["rows"],
                                    column_types=[c["type"] for c in actual["columns"]]).model_dump(mode="json")
    witness["outcome"] = "MATCH"
    validator(detailed_root).sql(SQLWitness.model_validate(witness))


@pytest.mark.parametrize("defect, expected_reason", [
    ("elapsed", "execution timestamp/duration accounting mismatch"),
    ("timeout", "successful execution exceeds timeout accounting budget"),
    ("memory", "execution measured memory exceeds resource limit"),
    ("stdout", "execution retained stdout exceeds byte limit"),
    ("stderr", "execution retained stderr exceeds byte limit"),
    ("result_bytes", "execution output byte accounting mismatch"),
    ("result_limit", "execution resource details inconsistent with successful result"),
])
def test_success_accounting_forgeries_are_rejected(detailed_root, defect, expected_reason):
    from datetime import datetime, timedelta

    from verified_data_factory.verification.receipt_models import SQLWitness

    root, _, _, _ = detailed_root
    witness = retained_sql(detailed_root, CORRECT_SQL, "accounting")
    execution = json.loads((root / witness["execution"]["path"]).read_text())
    if defect in {"elapsed", "timeout"}:
        execution["duration_ms"] = execution["resource_usage"]["duration_ms"] = 6000
        end = datetime.fromisoformat(execution["started_at"])
        if defect == "timeout":
            end += timedelta(seconds=6)
        execution["finished_at"] = end.isoformat()
    elif defect == "memory":
        execution["resource_usage"]["max_memory_mb"] = 1024
    elif defect == "stdout":
        execution["stdout"] = "nonempty"
    elif defect == "stderr":
        execution["stderr"] = "é"
        execution["resource_limits"]["max_stderr_bytes"] = 1  # UTF-8 bytes, not characters
    elif defect == "result_bytes":
        execution["resource_limits"]["max_result_bytes"] = 1
        execution["resource_usage"]["output_bytes"] = 0
    else:
        execution["resource_limits"]["max_result_bytes"] = 1
    witness["execution"] = write_ref(root, witness["execution"]["path"], execution)
    with pytest.raises(ValueError, match=expected_reason):
        validator(detailed_root).sql(SQLWitness.model_validate(witness))


def test_execution_accounting_accepts_only_bounded_millisecond_epsilon(detailed_root):
    from verified_data_factory.verification.receipt_models import SQLWitness

    root, _, _, _ = detailed_root
    witness = retained_sql(detailed_root, CORRECT_SQL, "epsilon")
    execution = json.loads((root / witness["execution"]["path"]).read_text())
    execution["duration_ms"] += 1
    execution["resource_usage"]["duration_ms"] += 1
    witness["execution"] = write_ref(root, "epsilon-plus-one.json", execution)
    validator(detailed_root).sql(SQLWitness.model_validate(witness))
    execution["duration_ms"] += 2
    execution["resource_usage"]["duration_ms"] += 2
    witness["execution"] = write_ref(root, "epsilon-plus-three.json", execution)
    with pytest.raises(ValueError, match="execution timestamp/duration accounting mismatch"):
        validator(detailed_root).sql(SQLWitness.model_validate(witness))


def test_actual_sandbox_collector_byte_conventions_accept_real_local_output(detailed_root):
    from verified_data_factory.sandbox.config import SandboxConfig
    from verified_data_factory.sandbox.executor import SandboxExecutor
    from verified_data_factory.sandbox.models import RunResult
    from verified_data_factory.verification.receipt_models import SQLWitness

    root, task, _, _ = detailed_root
    sample = {**task.tables["production_runs"][0], "group_key": "café" * 128,
              "status": "eligible", "amount": 3, "occurred_at": "2025-01-01 00:00:00"}
    index = add_targeted_fixture(detailed_root, {"production_runs": [sample]}, "unicode-rows.json")
    witness = retained_sql(detailed_root, CORRECT_SQL, "collector", index)
    execution = json.loads((root / witness["execution"]["path"]).read_text())
    payload = {**execution["result_data"], "duckdb_version": execution["duckdb_version"]}
    raw = json.dumps(payload).encode("utf-8")
    cfg = SandboxConfig(memory_mb=128, timeout_seconds=5,
                        max_result_bytes=execution["resource_usage"]["output_bytes"],
                        max_stdout_bytes=len(raw), max_stderr_bytes=1024)
    # Exercise the real collector on genuine local SQL output; no Docker runner
    # is instantiated and no container execution is claimed by this test.
    executor = object.__new__(SandboxExecutor)
    executor._config = cfg
    base = {key: execution[key] for key in ["execution_id", "task_id", "candidate_id", "started_at",
                                          "sandbox_image", "duckdb_version"]}
    base.pop("duckdb_version")  # collector obtains the engine version from its wire payload
    base.update(resource_limits=cfg.resource_limits(), sandbox_config_version=cfg.config_version)
    collected = executor._collect(base, execution["started_at"], RunResult(exit_code=0, stdout=raw, stderr=b""))
    assert collected.status == "SUCCEEDED"
    assert collected.resource_usage.output_bytes == cfg.max_result_bytes
    assert len(collected.stdout.encode("utf-8")) == cfg.max_stdout_bytes
    witness["execution"] = write_ref(root, "actual-collector.json", collected.model_dump(mode="json"))
    validator(detailed_root).sql(SQLWitness.model_validate(witness))
