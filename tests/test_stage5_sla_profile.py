"""Public-clause SLA witnesses must execute as typed semantic disagreements."""
import pytest

from scripts.phase3_diagnostic import _reference_sql
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.comparator import compare
from verified_data_factory.verification.oracle_registry import get_oracle
from verified_data_factory.verification.qualification.sla_profile import (
    CONTRACT,
    alternatives,
    challenge_specs,
    proofs,
)

pytest_plugins = ["tests.test_stage2_receipt_producer"]


def matches(task, sql, tables):
    connection = materialize_duckdb(task.schema_, tables)
    try:
        cursor = connection.execute(sql)
        description = cursor.description
        rows = [list(row) for row in cursor.fetchall()]
        expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, tables)
        return compare(expected, [column[0] for column in description], rows,
                       column_types=[str(column[1]) for column in description]).match
    finally:
        connection.close()


@pytest.mark.parametrize("rule", ["objective", "year", "status_filter", "group_by", "null_handling",
                                  "count_semantics", "empty_group_behavior", "output_columns", "order_by", "deadline_inclusive"])
def test_public_discriminator_is_a_real_wrong_answer(rule):
    task = generate_task(load_builtin_registry().get(CONTRACT, 1), 94001)
    reference = _reference_sql()[CONTRACT]
    proof = proofs(reference)[rule]
    assert matches(task, reference, proof["witness"])
    assert not matches(task, proof["wrong_sql"], proof["witness"])


def test_twenty_wrong_challenges_and_three_real_formulations():
    task = generate_task(load_builtin_registry().get(CONTRACT, 1), 94001)
    reference = _reference_sql()[CONTRACT]
    wrong = challenge_specs(reference)
    assert len({sql for sql, _ in wrong}) >= 20
    for sql, tables in wrong:
        assert not matches(task, sql, tables)
        assert all(matches(task, correct, tables) for correct in alternatives(reference))


def test_complete_public_rules_and_mutations_have_nullable_domain_proof(producer_root):
    from scripts.engineering_receipt_artifacts import ArtifactWriter
    from tests.test_stage2_receipt_producer import assert_receipt
    from verified_data_factory.verification.behavior_authority import public_behavior_map
    from verified_data_factory.verification.qualification.validation import DetailValidator

    writer = ArtifactWriter(producer_root, "sla-public-proof", CONTRACT, 1, ["pyproject.toml"])
    rules = writer.rules()
    assert_receipt(writer, "rules", rules)
    assert_receipt(writer, "mutation", writer.mutations(rules))
    nullable = next(rule for rule in rules.rules if rule.rule_id == "schema:fulfillments.delivered_at")
    assert nullable.disposition == "DOMAIN_CONFORMANCE"
    assert nullable.domain_tables is not None and nullable.invalid_tables is None
    checker = DetailValidator(writer.root, writer.task, public_behavior_map(writer.task), writer.sources, writer.thresholds)
    altered = nullable.model_copy(update={"domain_checks": {}})
    with pytest.raises(ValueError, match="declared type/nullability"):
        checker.rules(rules.model_copy(update={"rules": [altered if rule.rule_id == nullable.rule_id else rule for rule in rules.rules]}))


def test_full_sla_fuzz_retains_all_900_cases_and_actual_alternatives(producer_root):
    from scripts.engineering_receipt_artifacts import ArtifactWriter
    from tests.test_stage2_receipt_producer import assert_receipt

    writer = ArtifactWriter(producer_root, "sla-full-fuzz-proof", CONTRACT, 1, ["pyproject.toml"])
    formulations = alternatives(_reference_sql()[CONTRACT])
    detail = writer.fuzz(formulations)
    assert len(detail.cases) == 900
    assert all(len(case.alternatives) == 3 for case in detail.cases)
    data = assert_receipt(writer, "fuzz", detail)
    assert data["checks_run"] == 2700
    assert data["metrics"]["valid_random_cases"] == 900
