"""Public declarations, not chosen operators, define required coverage."""

import pytest

from tests.verify_sql_samples import CORRECT_SQL
from tests.verify_testkit import SimBackend, make_task
from verified_data_factory.task_engine import load_builtin_registry
from verified_data_factory.task_engine.fixtures import generate_fixture_tables
from verified_data_factory.task_engine.instruction import (
    build_instruction_context,
    render_instruction,
)
from verified_data_factory.task_engine.models import TaskInstance
from verified_data_factory.task_engine.validation import validate_task
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.models import ComparisonPolicy
from verified_data_factory.verification.mutations import MutationContext, run_mutation_checks
from verified_data_factory.verification.oracle_registry import get_oracle


def test_authority_retains_requirement_instruction_and_schema_declarations():
    task = make_task("sql.joins.simple")
    authority = public_behavior_map(task)
    assert authority.contract_id == task.template_id
    assert authority.contract_version == task.template_version
    assert authority.schema_version == 1
    assert {r.rule_id for r in authority.rules if r.origin == "requirements"} == set(
        task.requirements
    )
    assert any(r.origin == "instruction" for r in authority.rules)
    assert any(r.origin == "schema" and r.kind == "input_domain" for r in authority.rules)


def test_chosen_operator_cap_cannot_shrink_public_required_rules():
    task = make_task("sql.joins.simple")
    oracle = get_oracle(task.template_id, task.template_version)
    ctx = MutationContext(
        task, CORRECT_SQL[task.template_id], task.tables,
        oracle.fn(task.requirements, task.tables), SimBackend(), ComparisonPolicy(),
    )
    one = run_mutation_checks(ctx, max_mutations=1, min_score=0)
    many = run_mutation_checks(ctx, max_mutations=20, min_score=0)
    assert one.required_rules == many.required_rules
    assert set(one.required_rules) == set(public_behavior_map(task).semantic_rule_ids)
    assert not one.coverage_complete


def test_caller_requirement_subset_is_not_public_authority():
    task = make_task("sql.joins.simple")
    altered = task.model_copy(update={"requirements": {}})
    authority = public_behavior_map(altered)
    assert not authority.task_matches_public_contract
    assert authority.semantic_rule_ids == public_behavior_map(task).semantic_rule_ids


def test_unknown_contract_has_no_fabricated_generic_authority():
    task = make_task("sql.joins.simple").model_copy(update={"template_id": "sql.invented"})
    authority = public_behavior_map(task)
    assert not authority.task_matches_public_contract
    assert not authority.rules
    assert authority.blocked_reason == "unknown public contract/version"


def test_caller_cannot_replace_declared_instruction():
    task = make_task("sql.joins.simple")
    altered = task.model_copy(update={"instruction": "Return any rows."})
    authority = public_behavior_map(altered)
    assert not authority.task_matches_public_contract
    assert authority.declaration_sha256 == public_behavior_map(task).declaration_sha256


def test_unknown_public_version_is_blocked():
    task = make_task("sql.joins.simple").model_copy(update={"template_version": 999})
    authority = public_behavior_map(task)
    assert not authority.task_matches_public_contract
    assert authority.blocked_reason == "unknown public contract/version"


@pytest.mark.parametrize("template_id", list(CORRECT_SQL))
def test_builtin_public_authority_is_resolved_for_each_original_family(template_id):
    task = make_task(template_id)
    authority = public_behavior_map(task)
    assert authority.task_matches_public_contract, authority.blocked_reason
    assert set(task.requirements) <= set(authority.semantic_rule_ids)
    assert not set(authority.semantic_rule_ids) & set(authority.domain_rule_ids)
    assert len(authority.declaration_sha256) == 64


def test_caller_schema_nullability_cannot_erase_domain_obligation():
    task = make_task("sql.joins.simple")
    table = task.schema_[0]
    columns = [c.model_copy(update={"nullable": True}) for c in table.columns]
    altered_table = table.model_copy(update={"columns": columns})
    altered = task.model_copy(update={"schema_": [altered_table, *task.schema_[1:]]})
    authority = public_behavior_map(altered)
    assert not authority.task_matches_public_contract
    assert authority.domain_rule_ids == public_behavior_map(task).domain_rule_ids


def test_numerically_equal_year_with_different_type_is_not_public_authority():
    task = make_task("sql.aggregation.manufacturing_line_scrap", seed=94001)
    payload = task.model_dump(by_alias=True)
    payload["requirements"]["year"] = 2025.0
    altered = TaskInstance.model_validate(payload)
    validate_task(altered)
    assert altered.instruction == task.instruction
    assert type(altered.requirements["year"]) is float
    oracle = get_oracle(task.template_id, task.template_version)
    assert len(oracle.fn(task.requirements, task.tables).rows) == 3
    assert oracle.fn(altered.requirements, altered.tables).rows == []
    authority = public_behavior_map(altered)
    assert not authority.task_matches_public_contract
    assert authority.declaration_sha256 == public_behavior_map(task).declaration_sha256


@pytest.mark.parametrize("conflicting_first", [True, False])
def test_conflicting_duplicate_table_declarations_are_rejected_in_either_order(
    conflicting_first,
):
    task = make_task("sql.joins.simple")
    payload = task.model_dump(by_alias=True)
    original = payload["schema"][0]
    conflicting = {
        **original,
        "columns": [{**column, "nullable": True} for column in original["columns"]],
    }
    pair = [conflicting, original] if conflicting_first else [original, conflicting]
    payload["schema"] = [*pair, *payload["schema"][1:]]
    altered = TaskInstance.model_validate(payload)
    assert altered.instruction == task.instruction
    assert len(altered.schema_) == len(task.schema_) + 1
    authority = public_behavior_map(altered)
    assert not authority.task_matches_public_contract
    assert authority.blocked_reason == "duplicate task schema table declarations"


def test_caller_cannot_rewrite_generated_edge_instruction_binding():
    task = make_task("sql.aggregation.grouped")
    template = load_builtin_registry().get(task.template_id, task.template_version)
    payload = task.model_dump(by_alias=True)
    payload["edge_cases"] = []
    payload["instruction"] = render_instruction(template.instruction_template,
        build_instruction_context(tables=task.tables, requirements=task.requirements, edge_cases=[]))
    altered = TaskInstance.model_validate(payload)
    validate_task(altered)
    assert task.edge_cases and altered.instruction != task.instruction
    assert not public_behavior_map(altered).task_matches_public_contract


@pytest.mark.parametrize("seed", [0, 1, 301])
def test_authority_uses_actually_ensured_edges_not_all_declared_cases(seed):
    task = make_task("sql.aggregation.grouped", seed=seed)
    template = load_builtin_registry().get(task.template_id, task.template_version)
    _, ensured = generate_fixture_tables(template, seed)
    assert task.edge_cases == sorted(ensured)
    assert public_behavior_map(task).task_matches_public_contract
