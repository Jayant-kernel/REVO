"""Local qualification only: staged schema, raw validation, typed DuckDB proofs."""
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from verified_data_factory.sandbox.policy import check_policy
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.task_engine.template import load_template_file
from verified_data_factory.verification.comparator import compare
from verified_data_factory.verification.models import ExpectedResult
from verified_data_factory.verification.qualification import language_titles_profile as p
from verified_data_factory.verification.qualification.language_titles_candidate_transforms import (
    candidate_proofs,
)

ROOT = Path(__file__).resolve().parents[1]
STAGED = ROOT / "scratch/company_evaluation/new-contracts-v1/groups/joins"
SCHEMA = load_template_file(STAGED / "requested_language_titles.yaml").schema_definition


def matches(sql, tables):
    p.validate_rows(tables)
    assert check_policy(sql).allowed
    con = materialize_duckdb(SCHEMA, tables)
    try:
        con.execute("SET enable_external_access=false")
        cursor = con.execute(sql)
        description = cursor.description
        return compare(p.expected({}, tables), [column[0] for column in description],
                       [list(row) for row in cursor.fetchall()],
                       column_types=[str(column[1]) for column in description]).match
    finally:
        con.close()


def test_staged_semantics_and_public_coverage():
    original = yaml.safe_load((STAGED / "requested_language_titles.yaml").read_text())
    production = yaml.safe_load((ROOT / "templates/sql/joins/requested_language_titles.yaml").read_text())
    config = production.pop("generation_config")
    assert original == production
    assert config == {"business_fixture": "language_titles", "domain": "media_localization"}
    assert p.REFERENCE + ";" == " ".join((STAGED / "requested_language_titles.sql").read_text().split())
    public = p.proofs(p.REFERENCE)
    assert set(original["requirements"]) <= set(public)
    assert set(p.EDGE_PROOFS) == set(original["edge_cases"])
    assert set(p.EDGE_PROOFS.values()) <= set(public)
    assert set(original["edge_cases"]) <= set(public)
    assert p.STRUCTURAL_KEYS == set()
    assert p.DOMAIN_KEYS <= set(public)
    prose = original["instruction_template"]
    for key, substring in p.CLAUSES.values():
        assert key in public
        assert substring in prose
    assert "wrong_sql" in public["input_domain_rules"]  # No fake invalid-domain waiver.


def test_original_examples_and_bag_product():
    for case in json.loads((STAGED / "requested_language_titles.json").read_text()):
        expected = ExpectedResult.model_validate(case["expected"])
        actual = p.expected({}, case["tables"])
        assert compare(expected, actual.columns, actual.rows, column_types=actual.column_types).match
        assert all(matches(sql, case["tables"]) for sql in p.alternatives(p.REFERENCE))
    rows = p.expected({}, p.rich_fixture()).rows
    assert Counter(map(tuple, rows))[(1, "Book")] == 4
    assert Counter(map(tuple, rows))[(1, "Volume")] == 2
    assert [6, None] in rows and [7, ""] in rows and [8, None] in rows


RAW_CASES = [(table, column, value) for table, columns in p.SCHEMA.items()
             for column, kind in columns.items()
             for value in ([True, False, "10", 1.5, -2147483649, 2147483648]
                           if kind == "INTEGER" else [42, False, 1.5, [], {}])]


@pytest.mark.parametrize("table,column,value", RAW_CASES)
def test_raw_rejection_precedes_coercion(table, column, value):
    tables = p.rich_fixture()
    tables[table][0][column] = value
    with pytest.raises(ValueError, match=table + r"\." + column):
        p.expected({}, tables)


def test_exact_schema_required_null_and_nullable_conformance():
    for change in (lambda t: t.pop("translations"), lambda t: t.update(extra=[]),
                   lambda t: t["requests"][0].pop("language"),
                   lambda t: t["translations"][0].update(extra=1),
                   lambda t: t["requests"][0].update(request_id=None),
                   lambda t: t.update(requests=())):
        tables = p.rich_fixture()
        change(tables)
        with pytest.raises(ValueError):
            p.validate_rows(tables)
    tables = p.rich_fixture()
    tables["requests"][0]["request_id"] = None
    p.validate_rows(tables, allow_required_null=True)
    tables["requests"][0]["request_id"] = "1"
    with pytest.raises(ValueError):
        p.validate_rows(tables, allow_required_null=True)
    for table, columns in p.SCHEMA.items():
        for column in columns:
            checks = p.schema_checks(None, table, column)
            for probe in checks["raw_rejections"]:
                with pytest.raises(ValueError):
                    p.validate_rows(probe["tables"])
            for probe in checks["raw_conformance"]:
                assert set(probe["tables"]) == {"requests", "translations"}
                assert matches(p.REFERENCE, probe["tables"])


def test_every_proof_and_twenty_five_wrong_queries():
    wrong = p.failures(p.REFERENCE)
    assert len(wrong) == len(set(wrong.values())) == 25
    for sql, tables in p.challenge_specs(p.REFERENCE):
        assert matches(p.REFERENCE, tables)
        assert not matches(sql, tables), sql
    for key, proof in p.proofs(p.REFERENCE).items():
        if "wrong_sql" in proof:
            assert matches(p.REFERENCE, proof["witness"]), key
            assert not matches(proof["wrong_sql"], proof["witness"]), key
        else:
            with pytest.raises(ValueError):
                p.validate_rows(proof["witness"])


@pytest.mark.parametrize("sql", [p.REFERENCE,
    ('SELECT actual.request_id AS request_id, local.title AS title FROM requests actual LEFT JOIN translations local '
     'ON local.language=actual.language AND local.item_id=actual.item_id'),
    ('SELECT requests.request_id, translations.title FROM requests LEFT JOIN translations '
     'ON requests.language=translations.language AND requests.item_id=translations.item_id')])
def test_actual_candidate_discriminators_and_counterexamples(sql):
    public = p.proofs(p.REFERENCE)
    derived = candidate_proofs(sql, "SELECT 'not used'", public)
    assert derived is not None and set(derived) == set(public)
    semantic = {key: spec for key, spec in derived.items() if "wrong_sql" in spec}
    assert len(semantic) >= 15
    assert len({spec["wrong_sql"] for spec in semantic.values()}) >= 15
    for key, spec in semantic.items():
        assert spec["outcome"] == "UNEXECUTED_CANDIDATE_AST_RULE_SPEC"
        assert matches(sql, spec["witness"]), key
        assert not matches(spec["wrong_sql"], spec["witness"]), key
        # On an ordinary unique complete match, most faulty forms appear correct.
        ordinary = {"requests": [p.request()], "translations": [p.translation()]}
        if key not in {"output_columns", "output_types", "orphan"}:
            assert matches(spec["wrong_sql"], ordinary), key
    if "actual." in sql:
        assert "actual" in derived["composite_key"]["wrong_sql"]
        assert "local" in derived["composite_key"]["wrong_sql"]


def test_unsupported_ast_abstains_even_if_equivalent():
    for sql in [*p.alternatives(p.REFERENCE)[1:], *p.failures(p.REFERENCE).values(),
                p.REFERENCE + " WHERE TRUE", p.REFERENCE + " ORDER BY r.request_id",
                "SELECT * FROM (" + p.REFERENCE + ") wrapped", "SELECT * FROM requests",
                p.REFERENCE.replace("r.request_id,", "r.request_id AS wrong_name,"),
                p.REFERENCE + "; SELECT 1", "not SQL"]:
        assert candidate_proofs(sql, p.REFERENCE, p.proofs(p.REFERENCE)) is None, sql


def test_relation_discrimination_and_preconditions():
    for relation, wrong, before in p.relation_specs(p.REFERENCE):
        snapshot = deepcopy(before)
        after, reason = p.transform(before, relation)
        assert after is not None, reason
        assert before == snapshot
        assert Counter(map(tuple, p.expected({}, before).rows)) == Counter(map(tuple, p.expected({}, after).rows))
        assert matches(p.REFERENCE, after)
        assert matches(wrong, before)
        assert not matches(wrong, after)
    assert p.transform({"requests": [], "translations": []}, "LANGUAGE_NULL_KEYS")[0] is None
    assert p.transform(p.rich_fixture(), "unknown")[0] is None


def test_four_substantive_fixtures_and_empty_sides():
    frames = [p.fixture(seed, index) for seed, index in ((1, 0), (43, 1), (94001, 2), (1, 12))]
    assert len({json.dumps(frame, sort_keys=True) for frame in frames}) == 4
    assert p.fixture(43, 1) == frames[1]
    assert set().union(*(p.observed(frame)[2] for frame in frames)) == set(p.BEHAVIORS)
    frames.extend([{"requests": [p.request()], "translations": []},
                   {"requests": [], "translations": [p.translation()]},
                   {"requests": [p.request(1, None, None)], "translations": [p.translation(None, None)]}])
    for frame in frames:
        assert all(matches(sql, frame) for sql in p.alternatives(p.REFERENCE))


@pytest.mark.parametrize("seed", [1, 43, 94001])
def test_300_frame_actual_counts_and_local_sql(seed):
    counts = Counter()
    for index in range(300):
        tables = p.fixture(seed, index)
        policy, required, found = p.observed(tables)
        assert policy == "language-titles-observed-v1"  # Parent will add wire-policy registration.
        assert required == p.BEHAVIORS
        assert found <= set(required)
        counts.update(found)
        con = materialize_duckdb(SCHEMA, tables)
        try:
            con.execute("SET enable_external_access=false")
            wanted = p.expected({}, tables)
            for sql in p.alternatives(p.REFERENCE):
                assert check_policy(sql).allowed
                cursor = con.execute(sql)
                assert compare(wanted, [c[0] for c in cursor.description],
                               [list(row) for row in cursor.fetchall()],
                               column_types=[str(c[1]) for c in cursor.description]).match
        finally:
            con.close()
    assert counts["empty_input"] == 23
    assert all(counts[name] >= 20 for name in required), counts
    print(f"seed={seed} frames=300 SQL comparisons=900 behavior_counts={dict(sorted(counts.items()))}")


def test_observations_depend_on_rows_not_frame_labels():
    empty = {"requests": [], "translations": []}
    assert p.observed(empty)[2] == {"empty_input"}
    simple = {"requests": [p.request()], "translations": [p.translation()]}
    assert p.observed(simple)[2] == {"matched"}
    nulls = {"requests": [p.request(1, None, None)], "translations": []}
    assert p.observed(nulls)[2] == {"unmatched", "null_item", "null_language", "both_null"}
    reversed_keys = {name: [dict(reversed(list(row.items()))) for row in rows]
                     for name, rows in p.rich_fixture().items()}
    assert p.observed(reversed_keys) == p.observed(p.rich_fixture())


def test_literal_text_and_signed_ids_have_no_additional_domain_restrictions():
    for language in ("NULL", "null", "%", "_", "en-US", "中文", "\x00", " en ", ""):
        tables = {"requests": [p.request(0, -1, language), p.request(0, -1, language)],
                  "translations": [p.translation(-1, language, "NULL"),
                                   p.translation(-1, language + "x", "not matched")]}
        assert p.expected({}, tables).rows == [[0, "NULL"], [0, "NULL"]]
        assert all(matches(sql, tables) for sql in p.alternatives(p.REFERENCE))
