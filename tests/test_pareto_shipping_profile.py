"""Standalone staged-schema execution; intentionally not registered in shared dispatch."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from verified_data_factory.sandbox.policy import check_policy
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.task_engine.template import load_template_file
from verified_data_factory.verification.qualification import pareto_shipping_profile as p
from verified_data_factory.verification.qualification.pareto_shipping_candidate_transforms import (
    candidate_proofs,
    structural_checks,
)

ROOT = Path(__file__).resolve().parents[1]
STAGED = ROOT / "scratch/company_evaluation/new-contracts-v1/groups/dedup-subqueries"
TEMPLATE = load_template_file(STAGED / "templates/pareto_shipping.yaml")
TASK = SimpleNamespace(template_id=p.CONTRACT, template_version=1)


def execute(sql, tables):
    assert check_policy(sql).allowed, sql
    p.validate_rows(tables)
    con = materialize_duckdb(TEMPLATE.schema_definition, tables)
    try:
        con.execute("SET enable_external_access=false")
        result = con.execute(sql)
        columns = [c[0] for c in result.description]
        types = [str(c[1]) for c in result.description]
        return columns, types, [list(row) for row in result.fetchall()]
    finally:
        con.close()


def matches(sql, tables):
    wanted = p.expected({}, tables)
    return execute(sql, tables) == (wanted.columns, wanted.column_types, wanted.rows)


def test_public_semantics_and_clause_mapping_exactly_preserved():
    production = load_template_file(ROOT / "templates/sql/subqueries/pareto_shipping.yaml")
    assert production.requirements == TEMPLATE.requirements
    assert production.instruction_template == TEMPLATE.instruction_template
    assert production.schema_definition == TEMPLATE.schema_definition
    assert production.generation_config["business_fixture"] == "pareto_shipping"
    assert production.generation_config["domain"] == "shipping_logistics"
    public = p.proofs(p.REFERENCE)
    assert set(TEMPLATE.requirements) <= public.keys()
    assert p.DOMAIN_KEYS <= public.keys()
    assert p.STRUCTURAL_KEYS == {"not_exists_structure"}
    assert set(p.EDGE_PROOFS) == set(TEMPLATE.edge_cases)
    for key, substring in p.CLAUSES.values():
        assert key in public
        assert substring in TEMPLATE.instruction_template


def test_staged_authored_fixtures_reference_and_typed_oracle():
    import json

    reference = (STAGED / "references/pareto_shipping.sql").read_text()
    for frame in json.loads((STAGED / "fixtures/pareto_shipping.json").read_text()):
        assert p.expected({}, frame["tables"]).model_dump(mode="json") == frame["expected"]
        assert matches(reference, frame["tables"])
        for sql in p.alternatives(p.REFERENCE):
            assert matches(sql, frame["tables"])


@pytest.mark.parametrize("tables", [
    {"options": []}, {"options": [p.option(cost=None)]},
    {"options": [p.option(duration=None)]}, {"options": [p.option(cost=None, duration=None)]},
    {"options": [p.option(-2147483648, "", 0, p.MAX), p.option(p.MAX, "", p.MAX, 0)]},
    {"options": [p.option(-1), p.option(0), p.option(1, "a", 0, 0)]},
    p.rich_fixture(),
])
def test_correct_formulations_across_boundaries(tables):
    for sql in p.alternatives(p.REFERENCE):
        assert matches(sql, tables)
        assert structural_checks(TASK, sql)["status"] == "PASS"


@pytest.mark.parametrize("column,value", [(c, v) for c in p.FIELDS[2:] for v in
    (-1, p.MAX + 1, True, False, "1", 1.0)] + [("option_id", v) for v in
    (None, True, False, "1", 1.0, -2147483649, p.MAX + 1)] + [("lane", v) for v in
    (None, True, 1, 1.0)])
def test_raw_domain_rejects_without_coercion(column, value):
    row = p.option()
    row[column] = value
    with pytest.raises(ValueError):
        p.expected({}, {"options": [row]})


def test_exact_tables_fields_uniqueness_and_null_probe_only():
    invalid = [{}, {"options": [], "other": []}, {"options": [p.option(), p.option(cost=1)]},
               {"options": [{"option_id": 1}]}, {"options": [{**p.option(), "extra": 1}]},
               {"options": (p.option(),)}]
    for tables in invalid:
        with pytest.raises(ValueError):
            p.validate_rows(tables)
    p.validate_rows({"options": [{**p.option(), "option_id": None, "lane": None}]}, allow_required_null=True)
    with pytest.raises(ValueError):
        p.validate_rows({"options": [p.option(cost=True)]}, allow_required_null=True)
    for column in p.FIELDS:
        payload = p.schema_checks(TASK, "options", column)
        assert payload["raw_rejections"] and payload["raw_conformance"]
    assert p.schema_checks(TASK, "options", "option_id")["raw_conformance"][-1] == p.MAX


def test_all_wrong_queries_are_executable_distinct_semantic_kills():
    challenges = p.challenge_specs(p.REFERENCE)
    assert len({sql for sql, _ in challenges}) >= 20
    controls = set(p.structural_controls().values())
    assert not controls.intersection(sql for sql, _ in challenges)
    for sql, tables in challenges:
        assert not matches(sql, tables), sql


def test_all_individual_public_proofs():
    for key, spec in p.proofs(p.REFERENCE).items():
        if "wrong_sql" in spec:
            assert matches(p.REFERENCE, spec["witness"]), key
            assert not matches(spec["wrong_sql"], spec["witness"]), key
        elif key in p.DOMAIN_KEYS:
            with pytest.raises(ValueError):
                p.expected({}, spec["witness"])
        else:
            assert key in p.STRUCTURAL_KEYS
            assert matches(spec["structural_sql"], spec["witness"])
            assert structural_checks(TASK, spec["structural_sql"])["status"] == "FAIL"


@pytest.mark.parametrize("sql", p.alternatives(p.REFERENCE))
def test_candidate_derived_mutants_execute_and_discriminate(sql):
    public = p.proofs(p.REFERENCE)
    derived = candidate_proofs(sql, p.REFERENCE, public)
    assert derived is not None and derived.keys() == public.keys()
    for key, spec in derived.items():
        if "wrong_sql" in spec:
            assert matches(sql, spec["witness"]), key
            assert not matches(spec["wrong_sql"], spec["witness"]), (key, spec["wrong_sql"])
        elif key in p.STRUCTURAL_KEYS:
            assert matches(spec["structural_sql"], spec["witness"])
            assert structural_checks(TASK, spec["structural_sql"])["status"] == "FAIL"


def test_aliases_and_and_order_recognition_actual_attribution():
    sql = p.REFERENCE.replace("options p", "options competitor").replace("p.", "competitor.").replace(
        "options o", "options proposal").replace("o.", "proposal.").replace(
        "proposal.cost_cents IS NOT NULL AND proposal.duration_minutes IS NOT NULL",
        "proposal.duration_minutes IS NOT NULL AND proposal.cost_cents IS NOT NULL")
    derived = candidate_proofs(sql, p.REFERENCE, p.proofs(p.REFERENCE))
    assert derived is not None
    assert "competitor" in derived["threshold_operator"]["wrong_sql"]
    assert "proposal" in derived["threshold_operator"]["wrong_sql"]
    assert structural_checks(TASK, sql)["status"] == "PASS"
    assert matches(sql, p.rich_fixture())
    for spec in derived.values():
        if "wrong_sql" in spec:
            assert not matches(spec["wrong_sql"], spec["witness"])


def test_unsupported_forms_abstain_and_structure_controls_remain_semantically_correct():
    for sql in [p.REFERENCE + " LIMIT 1", "SELECT * FROM options", *p.failures(p.REFERENCE).values(),
                *p.structural_controls().values()]:
        assert candidate_proofs(sql, p.REFERENCE, p.proofs(p.REFERENCE)) is None, sql
    for sql in p.structural_controls().values():
        for tables in [p.rich_fixture(), {"options": []}, p.fixture(43, 1)]:
            assert matches(sql, tables)
        assert structural_checks(TASK, sql)["status"] == "FAIL"
    assert structural_checks(TASK, "not sql")["status"] == "INCONCLUSIVE"
    assert structural_checks(SimpleNamespace(template_id="other", template_version=1), p.REFERENCE) is None
    assert p.structural_checks(TASK, p.REFERENCE)["status"] == "PASS"
    assert p.candidate_proofs(p.REFERENCE, p.REFERENCE, p.proofs(p.REFERENCE)) is not None


def test_relations_have_valid_fresh_ids_and_discriminate():
    for identifier, wrong, before in p.relation_specs(p.REFERENCE):
        original = deepcopy(before)
        after, reason = p.transform(before, identifier)
        assert after is not None, reason
        assert before == original
        assert p.expected({}, before).rows == p.expected({}, after).rows
        assert matches(p.REFERENCE, after)
        assert matches(wrong, before) and not matches(wrong, after)
    assert p.transform({"options": []}, "PARETO_INCOMPLETE_COMPETITOR")[0] is None
    assert p.transform({"options": [p.option(cost=p.MAX)]}, "PARETO_EQUAL_DURATION_DOMINATED")[0] is None
    for identifier, _, _ in p.relation_specs(p.REFERENCE):
        after, _ = p.transform({"options": [p.option(0), p.option(1), p.option(p.MAX)]}, identifier)
        assert after is not None
        p.validate_rows(after)


def test_four_substantive_frames_and_900_observed_cases():
    frames = [p.fixture(1, 0), p.fixture(43, 1), p.fixture(94001, 2), p.fixture(1, 12)]
    assert len({repr(frame) for frame in frames}) == 4
    assert p.fixture(43, 1) == frames[1]
    for seed in (1, 43, 94001):
        counts = Counter()
        for index in range(300):
            tables = p.fixture(seed, index)
            policy, required, found = p.observed(tables)
            assert policy == "pareto-shipping-observed-v1"
            assert set(required) == set(p.BEHAVIORS)
            counts.update(found)
            assert matches(p.REFERENCE, tables), (seed, index)
        assert counts["empty_input"] == 23
        assert all(counts[name] >= 20 for name in required), counts
    for tables in frames:
        for sql in p.alternatives(p.REFERENCE):
            assert matches(sql, tables)
