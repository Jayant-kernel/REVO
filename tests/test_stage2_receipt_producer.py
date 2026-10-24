"""Genuine local producer positives, deliberately without authority/STRONG labels."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb
import pytest

from scripts.engineering_receipt_artifacts import (
    PRODUCER,
    ArtifactWriter,
    catalog_blockers,
)
from tests.test_business_tasks import SAAS_V2_CHAINED_JOIN_SQL
from tests.test_saas_v2_differential_sql import RECURSIVE_SQL
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification import receipt_validation as validation_module
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.readiness import qualify, receipt
from verified_data_factory.verification.receipt_models import SQLWitness
from verified_data_factory.verification.receipt_validation import DetailValidator, required_sources

SCRAP = "sql.aggregation.manufacturing_line_scrap"
SAAS = "sql.funnel.saas_activation_payment"
CORRECT = (
    "SELECT group_key, SUM(amount) AS total_amount FROM production_runs "
    "WHERE status='eligible' AND EXTRACT(YEAR FROM occurred_at)=2025 "
    "GROUP BY group_key ORDER BY group_key ASC"
)
ALTERNATIVES = [
    CORRECT,
    ("WITH scoped AS (SELECT * FROM production_runs WHERE status='eligible' "
    "AND EXTRACT(YEAR FROM occurred_at)=2025) SELECT group_key, SUM(amount) AS total_amount "
    "FROM scoped GROUP BY group_key ORDER BY group_key ASC"),
    ("SELECT group_key, SUM(amount) AS total_amount FROM production_runs "
    "WHERE occurred_at >= TIMESTAMP '2025-01-01' AND occurred_at < TIMESTAMP '2026-01-01' "
    "AND status='eligible' GROUP BY group_key ORDER BY group_key ASC"),
]


@pytest.fixture
def producer_root(tmp_path):
    live = Path(__file__).resolve().parents[1]
    paths = set(required_sources())
    for folder in ("scripts", "tests"):
        paths.update(p.relative_to(live).as_posix() for p in (live / folder).rglob("*.py"))
    paths.add("pyproject.toml")
    for relative in paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(live / relative, destination)
    return tmp_path


def writer(root, contract=SCRAP, version=1):
    return ArtifactWriter(root, "preliminary-local-proof", contract, version, ["pyproject.toml"])


def assert_receipt(producer, category, detail):
    reference = producer.receipt(category, detail)
    valid, reason = receipt(producer.root, reference.model_dump(), producer.task.template_id,
                            producer.task.template_version, category)
    assert valid is not None, reason
    assert reason == "fresh executed evidence"
    return json.loads((producer.root / reference.path).read_text())


def test_named_scrap_execution_probe(request, record_property):
    record_property("node_id", request.node.nodeid)
    record_property("contract_id", SCRAP)
    record_property("contract_version", "1")
    task = generate_task(load_builtin_registry().get(SCRAP, 1), 94001)
    from verified_data_factory.task_engine.fixtures import materialize_duckdb
    from verified_data_factory.verification.oracle_registry import get_oracle

    connection = materialize_duckdb(task.schema_, task.tables)
    try:
        assert [list(row) for row in connection.execute(CORRECT).fetchall()] == get_oracle(
            SCRAP, 1,
        ).fn(task.requirements, task.tables).rows
    finally:
        connection.close()


@pytest.mark.parametrize("contract,version,sql", [(SCRAP, 1, CORRECT),
                                                  (SAAS, 2, SAAS_V2_CHAINED_JOIN_SQL)],
                         ids=["scrap", "saas"])
def test_supported_local_execution_and_diversity(producer_root, contract, version, sql):
    producer = writer(producer_root, contract, version)
    diversity = producer.diversity()
    witness = producer.sql(sql, diversity.fixtures[0])
    assert witness.outcome == "MATCH"
    check = DetailValidator(producer.root, producer.task, public_behavior_map(producer.task),
                            producer.sources, producer.thresholds)
    check.sql(SQLWitness.model_validate(witness))
    assert check.run_count == 1
    data = json.loads((producer.root / witness.execution.path).read_text())
    assert data["sandbox_image"] == "local-stage2-duckdb"
    assert data["sandbox_image_digest"] is None
    assert data["resource_usage"]["max_memory_mb"] is None
    assert data["stdout"]
    assert_receipt(producer, "fixture_diversity", diversity)
    assert not qualify(producer.root, {"contract_id": contract, "contract_version": version})["eligible"]


def test_actual_named_test_xml_is_bound_and_validates(producer_root):
    producer = writer(producer_root)
    node = "tests/test_stage2_receipt_producer.py::test_named_scrap_execution_probe"
    detail = producer.named_tests([node])
    assert detail.nodes == {node: "passed"}
    assert_receipt(producer, "named_tests", detail)


def test_twenty_challenges_and_two_before_after_discriminators(producer_root):
    producer = writer(producer_root)
    row = {"record_id": 1, "entity_id": 1, "group_key": "g1", "amount": 1,
           "sequence": 1, "status": "eligible", "occurred_at": "2025-01-01 00:00:00"}
    tables = {"production_runs": [
        {**row, "record_id": i, "entity_id": i, "amount": amount, "group_key": group,
         "status": status, "occurred_at": at}
        for i, (amount, group, status, at) in enumerate([
            (1, "g1", "eligible", "2025-01-01 00:00:00"),
            (1, "g1", "eligible", "2025-01-01 00:00:00"),
            (-3, "g1", "eligible", "2025-01-01 00:00:00"),
            (7, "g2", "eligible", "2025-01-01 00:00:00"),
            (9, "g2", "ineligible", "2025-01-01 00:00:00"),
            (13, "g2", "eligible", "2024-01-01 00:00:00"),
        ], 1)
    ]}
    wrong = [CORRECT.replace("SUM(amount)", expression) for expression in (
        "COUNT(amount)", "AVG(amount)", "MAX(amount)", "MIN(amount)", "SUM(DISTINCT amount)",
        "SUM(ABS(amount))", "SUM(amount)+1", "SUM(amount)-1", "SUM(amount)*2", "SUM(amount)*0",
        "SUM(amount)+10", "SUM(amount)-10",
    )]
    wrong += [CORRECT.replace("=2025", "=2024"), CORRECT.replace("=2025", "=2026"),
              CORRECT.replace("status='eligible'", "status='ineligible'"),
              CORRECT.replace("status='eligible'", "TRUE"),
              CORRECT.replace("EXTRACT(YEAR FROM occurred_at)=2025", "TRUE"),
              CORRECT.replace("ASC", "DESC"), CORRECT.replace("AS total_amount", "AS wrong_amount"),
              "SELECT 'constant' AS group_key, 0 AS total_amount"]
    data = assert_receipt(producer, "challenge", producer.challenges(
        [(sql, tables) for sql in wrong], ALTERNATIVES,
    ))
    assert data["checks_run"] == 23
    assert data["metrics"]["witnessed_wrong"] == 20
    # Each wrong query matches before and is killed only by the actual transform.
    before = {"production_runs": [row]}
    relations = producer.relations(CORRECT, [
        ("SCRAP_ADDITIVITY", CORRECT.replace("SUM(amount)", "COUNT(amount)"), before),
        ("SCRAP_EXCLUDED_ROW", CORRECT.replace("status='eligible' AND ", ""), before),
    ])
    assert_receipt(producer, "relations", relations)


@pytest.mark.parametrize("contract,version,alternatives", [
    (SCRAP, 1, ALTERNATIVES),
    (SAAS, 2, [SAAS_V2_CHAINED_JOIN_SQL, RECURSIVE_SQL,
               "WITH retained_alternative AS (" + SAAS_V2_CHAINED_JOIN_SQL + ") "
               "SELECT group_key, total_amount FROM retained_alternative ORDER BY group_key ASC"]),
], ids=["scrap", "saas"])
def test_full_900_case_fuzz_has_2700_real_executions(producer_root, contract, version, alternatives):
    producer = writer(producer_root, contract, version)
    detail = producer.fuzz(alternatives)
    assert len(detail.cases) == 900
    assert all(len(case.alternatives) == 3 for case in detail.cases)
    data = assert_receipt(producer, "fuzz", detail)
    assert data["checks_run"] == 2700
    assert data["metrics"] == {"valid_random_cases": 900, "observed_coverage_pass": True,
                               "divergences": 0}


def test_stale_source_rejects_emission_and_history_is_not_overwritten(producer_root):
    producer = writer(producer_root)
    detail = producer.diversity()
    source = producer_root / PRODUCER
    source.write_text(source.read_text() + "\n# changed after collection\n")
    with pytest.raises(ValueError, match="missing or stale artifact"):
        producer.receipt("fixture_diversity", detail)
    assert not (producer.destination / "fixture_diversity-receipt.json").exists()
    with pytest.raises(FileExistsError):
        writer(producer_root)


def test_sql_failure_cannot_become_semantic_kill(producer_root):
    producer = writer(producer_root)
    with pytest.raises(ValueError, match="EXECUTION_ERROR execution is not semantic"):
        producer.sql("SELECT missing_column FROM production_runs", producer.fixture(producer.task.tables))
    retained = list(producer.destination.glob("*-execution.json"))
    assert len(retained) == 1
    assert json.loads(retained[0].read_text())["status"] == "EXECUTION_ERROR"
    assert not list(producer.destination.glob("*-receipt.json"))


def test_catalog_is_enumerated_and_v9_is_not_created(producer_root):
    blockers = catalog_blockers()
    registry = load_builtin_registry()
    assert len(blockers) == len({t.template_id for t in registry.list()})
    assert all(not item["eligible"] for item in blockers)
    with pytest.raises(ValueError, match="v9 awaits"):
        ArtifactWriter(producer_root, "qualified-receipts-v9", SCRAP, 1, [])
    assert not (producer_root / "qualified-receipts-v9").exists()


def test_category_ids_include_the_snapshot_not_only_contract_folder(producer_root):
    identifiers = []
    for snapshot in ("snapshot-a", "snapshot-b"):
        producer = ArtifactWriter(producer_root, f"{snapshot}/same-contract-v1", SCRAP, 1, ["pyproject.toml"])
        reference = producer.receipt("fixture_diversity", producer.diversity())
        identifiers.append(json.loads((producer_root / reference.path).read_text())["evidence_id"])
    assert len(set(identifiers)) == 2


@pytest.mark.parametrize("defect", ["fixture", "sql", "candidate", "execution"])
def test_validation_cache_rehashes_every_artifact(producer_root, defect):
    producer = writer(producer_root)
    witness = producer.sql(CORRECT, producer.fixture(producer.task.tables))
    checker = DetailValidator(producer.root, producer.task, public_behavior_map(producer.task),
                              producer.sources, producer.thresholds)
    reference = witness.fixture.tables if defect == "fixture" else getattr(witness, defect)
    with checker:
        checker.sql(witness)
        path = producer.root / reference.path
        path.write_text(path.read_text() + "\n ")
        with pytest.raises(ValueError, match="missing or stale artifact"):
            checker.sql(witness)
    assert checker._connection is None


@pytest.mark.parametrize("defect,reason", [
    ("expected", "fixture expected result differs"),
    ("fingerprint", "fixture fingerprint mismatch"),
    ("comparison", "retained comparison differs"),
    ("outcome", "SQL outcome differs"),
    ("candidate", "candidate/task/SQL binding mismatch"),
    ("execution", "unsuccessful or inconsistent retained execution"),
])
def test_validation_cache_binds_full_metadata_and_updated_refs(producer_root, defect, reason):
    producer = writer(producer_root)
    witness = producer.sql(CORRECT, producer.fixture(producer.task.tables))
    checker = DetailValidator(producer.root, producer.task, public_behavior_map(producer.task),
                              producer.sources, producer.thresholds)
    altered = witness
    if defect == "expected":
        expected = witness.fixture.expected.model_copy(update={"rows": []})
        altered = witness.model_copy(update={"fixture": witness.fixture.model_copy(
            update={"expected": expected},
        )})
    elif defect == "fingerprint":
        altered = witness.model_copy(update={"fixture": witness.fixture.model_copy(
            update={"fingerprint": "0" * 64},
        )})
    elif defect == "comparison":
        altered = witness.model_copy(update={"comparison": witness.comparison.model_copy(
            update={"match": False},
        )})
    elif defect == "outcome":
        altered = witness.model_copy(update={"outcome": "KILLED_WRONG_ANSWER"})
    else:
        reference = getattr(witness, defect)
        payload = json.loads((producer.root / reference.path).read_text())
        payload["task_id" if defect == "candidate" else "execution_id"] = "altered"
        altered = witness.model_copy(update={defect: producer.write("altered.json", payload)})
    with checker:
        checker.sql(witness)
        checker.sql(witness)
        assert checker.run_count == 1
        with pytest.raises(ValueError, match=reason):
            checker.sql(altered)
    assert checker._connection is None


def test_one_scoped_connection_and_unique_execution_cache(producer_root, monkeypatch):
    producer = writer(producer_root)
    fixture = producer.fixture(producer.task.tables)
    witnesses = producer.sql_many(ALTERNATIVES, fixture)
    connections = []
    materialize = validation_module.materialize_duckdb

    def tracked(*args, **kwargs):
        connection = materialize(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(validation_module, "materialize_duckdb", tracked)
    checker = DetailValidator(producer.root, producer.task, public_behavior_map(producer.task),
                              producer.sources, producer.thresholds)
    with checker:
        for witness in witnesses:
            checker.sql(witness)
            checker.sql(witness)
        assert checker.run_count == 3
        assert len(connections) == 1
        # Returned mutable rows cannot corrupt the verified snapshot/cache.
        tables = checker.fixture(fixture)
        tables["production_runs"][0]["amount"] = 999999
        assert checker.fixture(fixture) != tables
    assert checker._connection is None
    with pytest.raises(duckdb.ConnectionException):
        connections[0].execute("SELECT 1")
    # A new validation scope cannot reuse the previous successful execution cache.
    with checker:
        checker.sql(witnesses[0])
        assert checker.run_count == 1
        assert len(connections) == 2


@pytest.mark.parametrize("change", ["task", "oracle", "comparison"])
def test_cache_cannot_cross_task_or_version_binding(producer_root, monkeypatch, change):
    producer = writer(producer_root)
    witness = producer.sql(CORRECT, producer.fixture(producer.task.tables))
    connections = []
    materialize = validation_module.materialize_duckdb

    def tracked(*args, **kwargs):
        connection = materialize(*args, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(validation_module, "materialize_duckdb", tracked)
    checker = DetailValidator(producer.root, producer.task, public_behavior_map(producer.task),
                              producer.sources, producer.thresholds)
    with checker:
        checker.sql(witness)
        if change == "task":
            checker.task = checker.task.model_copy(update={"seed": checker.task.seed + 1})
        elif change == "comparison":
            monkeypatch.setattr(validation_module, "COMPARISON_VERSION", "changed-test-version")
        else:
            from types import SimpleNamespace
            original = validation_module.get_oracle

            def changed(*args):
                oracle = original(*args)
                return SimpleNamespace(fn=oracle.fn, oracle_version=oracle.oracle_version + 1)

            monkeypatch.setattr(validation_module, "get_oracle", changed)
        checker.sql(witness)
        assert len(connections) == 2
        assert checker.run_count == 1
