"""Local evidence only; deliberately bypasses unmodified registration/wire policy."""
from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb
import pytest
import yaml

from verified_data_factory.verification.qualification import (
    queue_batches_candidate_transforms as ast,
)
from verified_data_factory.verification.qualification import queue_batches_profile as p

ROOT = Path(__file__).resolve().parents[1]
STAGED = ROOT / "scratch/company_evaluation/new-contracts-v1/groups/retention-windows"
TASK = SimpleNamespace(template_id=p.CONTRACT, template_version=1)


def execute(connection: Any, sql: str, tables: p.Tables) -> tuple[list[str], list[str], list[Any]]:
    p.validate_rows(tables)
    connection.execute("CREATE OR REPLACE TABLE submissions(submission_id INTEGER,queue VARCHAR,submitted_at TIMESTAMP)")
    if tables["submissions"]:
        connection.executemany("INSERT INTO submissions VALUES (?,?,?)",
                               [tuple(row[c] for c in p.SCHEMA["submissions"])
                                for row in tables["submissions"]])
    cursor = connection.execute(sql)
    return ([d[0] for d in cursor.description], [str(d[1]) for d in cursor.description],
            [list(row) for row in cursor.fetchall()])


def matches(connection: Any, sql: str, tables: p.Tables) -> bool:
    expected = p.expected({}, tables)
    return execute(connection, sql, tables) == (expected.columns, expected.column_types, expected.rows)


@pytest.fixture
def connection() -> Any:
    with duckdb.connect(config={"enable_external_access": "false"}) as conn:
        yield conn


def test_staging_and_four_fixtures(connection: Any) -> None:
    staged = yaml.safe_load((STAGED / "templates/queue_batches.yaml").read_text())
    actual = yaml.safe_load((ROOT / "templates/sql/windows/queue_batches.yaml").read_text())
    assert actual.pop("generation_config") == {"business_fixture": "queue_batches", "domain": "intake_operations"}
    assert actual == staged
    assert "using NTILE(3)" in actual["instruction_template"]
    for _, phrase in p.CLAUSES.values():
        assert phrase in actual["instruction_template"], phrase
    assert " ".join((STAGED / "references/queue_batches.sql").read_text().split()).rstrip(";") == p.REFERENCE
    fixtures = json.loads((STAGED / "fixtures/queue_batches.json").read_text())
    for fixture in fixtures:
        expected = p.expected({}, fixture["tables"])
        assert expected.rows == fixture["expected"]["rows"]
    tables = [f["tables"] for f in fixtures] + [p.boundary_rich_fixture(), {"submissions": []}]
    for frame in tables:
        for sql in p.alternatives(p.REFERENCE):
            assert matches(connection, sql, frame)
            assert ast.structural_checks(TASK, sql)["status"] == "PASS"


def test_wrong_queries_are_executable_discriminated_and_distinct(connection: Any) -> None:
    wrong = p.failures(p.REFERENCE)
    assert len(set(wrong.values())) == len(wrong) >= 20
    assert p.structural_control() not in wrong.values()
    for label, sql in wrong.items():
        assert not matches(connection, sql, p.rich_fixture()), label
    print(f"distinct executable wrong queries: {len(wrong)}; all discriminated")


def test_all_public_and_actual_candidate_proofs(connection: Any) -> None:
    public = p.proofs(p.REFERENCE)
    assert {p.CLAUSES[c][0] for c in p.CLAUSES} <= set(public)
    assert p.DOMAIN_KEYS | p.STRUCTURAL_KEYS | set(p.EDGE_PROOFS) <= set(public)
    for key, spec in public.items():
        if key in p.DOMAIN_KEYS:
            with pytest.raises(ValueError):
                p.validate_rows(spec["witness"])
        elif key in p.STRUCTURAL_KEYS:
            assert matches(connection, spec["structural_sql"], spec["witness"])
            assert ast.structural_checks(TASK, spec["structural_sql"])["status"] == "FAIL"
        else:
            assert not matches(connection, spec["wrong_sql"], spec["witness"]), key
    for candidate in p.alternatives(p.REFERENCE) + [p.alternatives(p.REFERENCE)[2].replace("s.", "src.").replace("submissions s", "submissions src")]:
        result = ast.candidate_proofs(candidate, p.REFERENCE, public)
        assert result is not None
        for key, spec in result.items():
            if key in p.DOMAIN_KEYS:
                continue
            if key in p.STRUCTURAL_KEYS:
                assert "wrong_sql" not in spec
                assert matches(connection, spec["structural_sql"], spec["witness"])
                assert ast.structural_checks(TASK, spec["structural_sql"])["status"] == "FAIL"
            else:
                assert not matches(connection, spec["wrong_sql"], spec["witness"]), (candidate, key)
        if "src." in candidate:
            assert 'src.' in result["partition_by"]["wrong_sql"]
    print(f"public proofs: {len(public)}; native candidate forms: 4; structural controls MATCH/FAIL")


def test_unknown_native_and_decorative_are_not_proof() -> None:
    unsupported = p.REFERENCE.replace("NTILE(3)", "NTILE(1+2)")
    assert ast.candidate_proofs(unsupported, p.REFERENCE, p.proofs(p.REFERENCE)) is None
    assert ast.structural_checks(TASK, unsupported)["status"] == "INCONCLUSIVE"
    decorative = f"WITH unused AS ({p.REFERENCE}) SELECT submission_id,CAST(1 AS BIGINT) AS batch_number FROM submissions ORDER BY submission_id"
    assert ast.structural_checks(TASK, decorative)["status"] == "FAIL"
    assert ast.candidate_proofs(decorative, p.REFERENCE, p.proofs(p.REFERENCE)) is None
    assert ast.structural_checks(TASK, "SELECT !!!")["status"] == "INCONCLUSIVE"
    for old, new in [("PARTITION BY queue", "PARTITION BY LOWER(queue)"),
                     ("NULLS LAST", "NULLS FIRST"),
                     (", submission_id ASC", ""),
                     ("NTILE(3)", "NTILE(4)"),
                     ("submission_id ASC)", "submission_id ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)")]:
        changed = p.REFERENCE.replace(old, new)
        assert ast.candidate_proofs(changed, p.REFERENCE, p.proofs(p.REFERENCE)) is None
        assert ast.structural_checks(TASK, changed)["status"] == "INCONCLUSIVE"


def test_equivalent_floor_control_not_a_semantic_kill(connection: Any) -> None:
    equivalent = p.failures(p.REFERENCE)["floor_proportional"].replace(
        "submission_id))*3", "submission_id)-1)*3")
    for tables in [p.rich_fixture(), {"submissions": []},
                   {"submissions": [p.submission(1), p.submission(2)]}]:
        assert matches(connection, equivalent, tables)
    assert equivalent not in p.failures(p.REFERENCE).values()
    assert ast.structural_checks(TASK, equivalent)["status"] == "FAIL"


@pytest.mark.parametrize("dtype", ["INTEGER", "BIGINT"])
@pytest.mark.parametrize("candidate", p.alternatives(p.REFERENCE))
def test_output_cast_is_structural_only(connection: Any, dtype: str, candidate: str) -> None:
    window = "NTILE(3) OVER (PARTITION BY {0}queue ORDER BY {0}submitted_at ASC NULLS LAST, {0}submission_id ASC)"
    prefix = "s." if "submissions s" in candidate else ""
    expression = window.format(prefix)
    cast = candidate.replace(expression, f"CAST({expression} AS {dtype})")
    assert cast != candidate
    assert ast.structural_checks(TASK, cast)["status"] == "PASS"
    assert matches(connection, cast, p.rich_fixture()) is (dtype == "BIGINT")
    assert ast.candidate_proofs(cast, p.REFERENCE, p.proofs(p.REFERENCE)) is None


def test_raw_gate_and_schema_probes() -> None:
    for column in p.SCHEMA["submissions"]:
        checks = p.raw_schema_checks(TASK, "submissions", column)
        assert checks["raw_rejections"] and checks["raw_conformance"]
    for tables in ({}, {"submissions": ()}, {"submissions": [{}]},
                   {"submissions": [p.submission(1), p.submission(1, "different")]}):
        with pytest.raises(ValueError):
            p.validate_rows(tables)
    tables = {"submissions": [p.submission(1)]}
    tables["submissions"][0]["queue"] = None
    p.validate_rows(tables, allow_required_null=True)
    with pytest.raises(ValueError):
        p.validate_rows(tables)
    assert p.expected({}, {"submissions": [p.submission(1), p.submission(2)]}).rows == [[1, 1], [2, 2]]


def test_relations_discriminate_and_preserve_unique_ids(connection: Any) -> None:
    for relation, wrong, before in p.relation_specs(p.REFERENCE):
        saved = deepcopy(before)
        after, reason = p.transform(before, relation)
        assert after is not None, reason
        assert before == saved
        p.validate_rows(after)
        ids = {r["submission_id"] for r in before["submissions"]}
        original = p.expected({}, before).rows
        assert matches(connection, wrong, before), relation
        assert not matches(connection, wrong, after), relation
        assert p.expected({}, after).rows == original
        assert [r for r in p.expected({}, after).rows if r[0] in ids] == original
        first = [r for r in execute(connection, wrong, before)[2] if r[0] in ids]
        second = [r for r in execute(connection, wrong, after)[2] if r[0] in ids]
        assert first != second, relation
    assert p.transform({"submissions": []}, "QUEUE_RELABEL")[0] is None
    assert p.transform({"submissions": []}, "QUEUE_REVERSE_INPUT")[0] is None
    assert p.transform(p.rich_fixture(), "UNKNOWN")[0] is None


@pytest.mark.parametrize("seed", [1, 43, 94001])
def test_900_frames_actual_behavior_and_typed_sql(connection: Any, seed: int) -> None:
    counts: Counter[str] = Counter()
    for index in range(300):
        tables = p.fixture(seed, index)
        assert tables == p.fixture(seed, index)
        version, mandatory, found = p.observed(tables)
        assert version == "queue-batches-observed-v1" and mandatory == p.BEHAVIORS
        counts.update(found)
        assert matches(connection, p.REFERENCE, tables)
        assert matches(connection, p.structural_control(), tables)
    assert set(counts) == set(p.BEHAVIORS)
    assert min(counts.values()) >= 20
    assert counts["empty_input"] == 23
    print(f"seed={seed} frames=300 typed native/arithmetic MATCH=600 behaviors={dict(sorted(counts.items()))}")
