"""Standalone staged-schema execution: not production dispatch certification."""
import importlib.util
import json
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest
import yaml

from verified_data_factory.task_engine.template import load_template_file
from verified_data_factory.verification.comparator import compare
from verified_data_factory.verification.models import ExpectedResult
from verified_data_factory.verification.qualification import renewal_coverage_profile as p

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "scratch/company_evaluation/new-contracts-v1"
GROUP = STAGE / "groups/retention-windows"
SCHEMA = load_template_file(GROUP / "templates/renewal_coverage.yaml").schema_definition


def matches(sql, tables, con=None):
    p.validate_rows(tables)
    owned = con is None
    con = con or duckdb.connect(config={"enable_external_access": "false"})
    try:
        for table in SCHEMA:
            con.execute(f'DROP TABLE IF EXISTS "{table.name}"')
            fields = ",".join(f'"{c.name}" {c.type}' for c in table.columns)
            con.execute(f'CREATE TABLE "{table.name}" ({fields})')
            rows = [[row[c.name] for c in table.columns] for row in tables[table.name]]
            if rows:
                con.executemany(f'INSERT INTO "{table.name}" VALUES ({",".join("?" for c in table.columns)})', rows)
        cursor = con.execute(sql)
        description = cursor.description
        return compare(p.expected({}, tables), [c[0] for c in description],
                       [list(r) for r in cursor.fetchall()], column_types=[str(c[1]) for c in description]).match
    finally:
        if owned:
            con.close()


def test_exact_staging_and_prose():
    staged = yaml.safe_load((GROUP / "templates/renewal_coverage.yaml").read_text())
    new = yaml.safe_load((ROOT / "templates/sql/retention/renewal_coverage.yaml").read_text())
    assert new.pop("generation_config") == {"business_fixture": "renewal_coverage", "domain": "membership_services"}
    assert new == staged
    assert p.REFERENCE + ";" == " ".join((GROUP / "references/renewal_coverage.sql").read_text().split())
    proofs = p.proofs(p.REFERENCE)
    assert set(staged["requirements"]) <= proofs.keys()
    assert p.DOMAIN_KEYS <= proofs.keys()
    assert p.STRUCTURAL_KEYS == set()
    assert set(p.EDGE_PROOFS) == set(staged["edge_cases"])
    for key, substring in p.CLAUSES.values():
        assert key in proofs
        assert substring in staged["instruction_template"]


def test_examples_four_fixtures_and_all_wrong_queries():
    cases = json.loads((GROUP / "fixtures/renewal_coverage.json").read_text())
    for case in cases:
        assert p.expected({}, case["tables"]) == ExpectedResult.model_validate(case["expected"])
    fixtures = [c["tables"] for c in cases] + [p.rich_fixture(), {"episodes": [], "renewals": []}]
    for t in fixtures:
        for sql in p.alternatives(p.REFERENCE):
            assert matches(sql, t), sql
    wrong = p.failures(p.REFERENCE)
    assert len(wrong) == len(set(wrong.values())) >= 20
    for name, sql in wrong.items():
        assert not matches(sql, p.rich_fixture()), name
    for key, proof in p.proofs(p.REFERENCE).items():
        if "wrong_sql" in proof:
            assert matches(p.REFERENCE, proof["witness"]), key
            assert not matches(proof["wrong_sql"], proof["witness"]), key
        else:
            with pytest.raises(ValueError):
                p.validate_rows(proof["witness"])


def test_strict_domains_and_staging_timestamp_agreement():
    spec = importlib.util.spec_from_file_location("renewal_stageverify", STAGE / "verify_staging.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for table in SCHEMA:
        for col in table.columns:
            probes = p.schema_checks(None, table.name, col.name)
            for item in probes["raw_rejections"]:
                with pytest.raises(ValueError):
                    p.validate_rows(item["tables"])
                if col.type == "TIMESTAMP" and type(item["value"]) is str:
                    with pytest.raises((ValueError, AssertionError)):
                        module.value_check(item["value"], col)
            for item in probes["raw_conformance"]:
                p.validate_rows(item["tables"])
                if col.type == "TIMESTAMP" and type(item["value"]) is str:
                    module.value_check(item["value"], col)
                assert matches(p.REFERENCE, item["tables"])
    for change in [lambda t: t.pop("episodes"), lambda t: t.update(extra=[]),
                   lambda t: t["episodes"][0].pop("member_id"),
                   lambda t: t["episodes"][0].update(expires_at=datetime(2025, 1, 1, tzinfo=UTC))]:
        t = p.rich_fixture()
        change(t)
        with pytest.raises(ValueError):
            p.validate_rows(t)
    t = p.rich_fixture()
    t["episodes"][0]["member_id"] = None
    p.validate_rows(t, allow_required_null=True)
    with pytest.raises(ValueError):
        p.expected({}, t)
    t["episodes"][0]["member_id"] = True
    with pytest.raises(ValueError):
        p.validate_rows(t, allow_required_null=True)


def test_microsecond_boundaries_cross_year_stitch_and_extremes():
    rows = dict(p.expected({}, p.rich_fixture()).rows)
    assert rows[1] is True and rows[2] is False and rows[3] is False and rows[4] is False
    assert rows[5] is False and rows[6] is False and rows[10] is True and rows[11] is True
    assert 12 not in rows and 13 not in rows
    t = {"episodes": [p.episode(1, 1, "9999-12-31T23:59:59.999999"),
                      p.episode(2, 1, "0001-01-01T00:00:00")], "renewals": []}
    assert p.expected({}, t).rows == []
    assert matches(p.REFERENCE, t)
    t = {"episodes": [p.episode(expiry="2025-12-31T23:59:59.999999")],
         "renewals": [p.renewal(begin="2025-12-31T23:59:59.999999", end="2026-01-14T23:59:59.999999")]}
    assert p.expected({}, t).rows == [[1, True]]
    assert matches(p.REFERENCE, t)
    t["renewals"][0]["ends_at"] = "2026-01-14T23:59:59.999998"
    assert p.expected({}, t).rows == [[1, False]]
    assert matches(p.REFERENCE, t)


CANDIDATES = p.alternatives(p.REFERENCE) + [
    p.REFERENCE.replace("e.", "actual.").replace("episodes e", "episodes actual").replace("r.", "local.").replace("renewals r", "renewals local"),
    p.REFERENCE.replace("e.expires_at>=TIMESTAMP '2025-01-01' AND e.expires_at<TIMESTAMP '2026-01-01'", "YEAR(e.expires_at)=2025").replace("INTERVAL '14 days'", "INTERVAL 14 DAY"),
    p.REFERENCE.replace("TIMESTAMP '2025-", "DATE '2025-").replace("TIMESTAMP '2026-", "DATE '2026-").replace("14 days", "336 hours"),
    p.REFERENCE.replace("EXISTS (", "CASE WHEN EXISTS (").replace(") AS covered FROM", ") THEN TRUE ELSE FALSE END AS covered FROM")]
CANDIDATES.append(p.REFERENCE.replace(
    "e.expires_at>=TIMESTAMP '2025-01-01' AND e.expires_at<TIMESTAMP '2026-01-01'",
    "EXTRACT(YEAR FROM e.expires_at)=2025").replace("14 days", "2 weeks"))


@pytest.mark.parametrize("sql", CANDIDATES)
def test_actual_candidate_ast_mutants(sql):
    public = p.proofs(p.REFERENCE)
    derived = p.candidate_proofs(sql, "SELECT 'not canonical'", public)
    assert derived is not None and derived.keys() == public.keys()
    semantic = [v["wrong_sql"] for v in derived.values() if "wrong_sql" in v]
    assert len(set(semantic)) >= 15
    for key, proof in derived.items():
        if "wrong_sql" in proof:
            assert proof["outcome"] == "UNEXECUTED_CANDIDATE_AST_RULE_SPEC"
            assert matches(sql, proof["witness"]), key
            assert not matches(proof["wrong_sql"], proof["witness"]), key
    if "actual." in sql:
        assert 'actual.' in derived["member"]["wrong_sql"]


def test_unsupported_unknown():
    for sql in [*p.failures(p.REFERENCE).values(), "SELECT 1", "not SQL", p.REFERENCE + "; SELECT 1",
                p.REFERENCE.replace("AS covered", "AS wrong_name"),
                p.REFERENCE.replace("WHERE e.expires_at", "WHERE e.member_id>0 AND e.expires_at")]:
        assert p.candidate_proofs(sql, p.REFERENCE, p.proofs(p.REFERENCE)) is None, sql


def test_two_discriminating_relations():
    for relation, wrong, before in p.relation_specs(p.REFERENCE):
        snapshot = deepcopy(before)
        after, reason = p.transform(before, relation)
        assert after is not None, reason
        assert before == snapshot
        assert p.expected({}, before) == p.expected({}, after)
        assert matches(wrong, before)
        assert not matches(wrong, after)
        assert matches(p.REFERENCE, after)
    assert p.transform({"episodes": [], "renewals": []}, "RENEWAL_ADJACENT")[0] is None
    assert p.transform(p.rich_fixture(), "unknown")[0] is None


def test_900_frames_actual_behavior_counts_and_sql_comparisons():
    con = duckdb.connect(config={"enable_external_access": "false"})
    try:
        for seed in (1, 43, 94001):
            counts = Counter()
            for index in range(300):
                t = p.fixture(seed, index)
                assert t == p.fixture(seed, index)
                version, mandatory, found = p.observed(t)
                assert version == "renewal-coverage-observed-v1" and mandatory == p.BEHAVIORS
                counts.update(found)
                for sql in p.alternatives(p.REFERENCE):
                    assert matches(sql, t, con), (seed, index, sql)
            assert counts["empty_input"] == 23
            assert all(counts[b] >= 20 for b in mandatory), counts
            print(f"seed={seed} frames=300 sql_comparisons=900 behaviors={dict(sorted(counts.items()))}")
    finally:
        con.close()
