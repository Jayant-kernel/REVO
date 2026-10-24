"""Complete public maps require clause-specific executed SQL, not claimed subsets."""
import pytest

from tests.test_stage2_receipt_producer import SAAS, SCRAP, assert_receipt, writer
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.receipt_validation import DetailValidator

pytest_plugins = ["tests.test_stage2_receipt_producer"]


@pytest.mark.parametrize("contract,version", [(SCRAP, 1), (SAAS, 2)])
def test_complete_rules_and_mutations(producer_root, contract, version):
    producer = writer(producer_root, contract, version)
    rules = producer.rules()
    assert_receipt(producer, "rules", rules)
    mutations = producer.mutations(rules)
    assert_receipt(producer, "mutation", mutations)
    checker = DetailValidator(producer.root, producer.task, public_behavior_map(producer.task),
                              producer.sources, producer.thresholds)
    with pytest.raises(ValueError, match="complete public ledger"):
        checker.rules(rules.model_copy(update={"rules": rules.rules[:-1]}))
    mutant = mutations.mutants[0]
    unrelated = next(r for r in mutations.required_rules if r not in mutant.rule_ids)
    changed = mutant.model_copy(update={"rule_ids": [unrelated]})
    with pytest.raises(ValueError, match="attribution"):
        checker.mutations(mutations.model_copy(update={"mutants": [changed, *mutations.mutants[1:]]}))
    with pytest.raises(ValueError, match="public authority"):
        checker.mutations(mutations.model_copy(update={"required_rules": mutations.required_rules[:-1]}))
    schema = next(r for r in rules.rules if r.rule_id.endswith(".amount"))
    for altered in (
        schema.model_copy(update={"domain_checks": {}}),
        schema.model_copy(update={"domain_checks": {**schema.domain_checks, "type": "VARCHAR"}}),
    ):
        changed_rules = [altered if r.rule_id == schema.rule_id else r for r in rules.rules]
        with pytest.raises(ValueError, match="declared type/nullability"):
            checker.rules(rules.model_copy(update={"rules": changed_rules}))
    year = next(r for r in rules.rules if r.rule_id == "year")
    altered = year.model_copy(update={"source_clause": "Caller-invented public clause"})
    with pytest.raises(ValueError, match="source attribution"):
        checker.rules(rules.model_copy(update={
            "rules": [altered if r.rule_id == "year" else r for r in rules.rules],
        }))


@pytest.mark.parametrize("contract,version", [(SCRAP, 1), (SAAS, 2)])
def test_instruction_clauses_have_distinct_behavior_obligations(contract, version):
    from verified_data_factory.task_engine import generate_task, load_builtin_registry

    authority = public_behavior_map(generate_task(load_builtin_registry().get(contract, version), 94001))
    clauses = {r.rule_id: r.proof_key for r in authority.rules if r.origin == "instruction"}
    assert "instruction:declared" not in clauses
    if contract == SCRAP:
        assert clauses["instruction:line"] == "group_by"
        assert clauses["instruction:year"] == "year"
        assert clauses["instruction:ascending"] == "order_by"
        assert clauses["instruction:eligible"] == "empty_group_behavior"
    else:
        assert clauses["instruction:sum_by_segment"] == "group_by_segment"
        assert clauses["instruction:matched_payment"] == "repeat_policy"
        assert clauses["instruction:entity_group"] == "entity_group"


def test_unmapped_contract_keeps_opaque_obligations():
    from verified_data_factory.task_engine import generate_task, load_builtin_registry
    from verified_data_factory.verification.public_rule_proofs import public_proofs

    task = generate_task(load_builtin_registry().get("sql.joins.simple"), 94001)
    authority = public_behavior_map(task)
    assert not authority.granular
    assert "instruction:declared" in authority.semantic_rule_ids
    with pytest.raises(ValueError, match="coverage unresolved"):
        public_proofs(task)
