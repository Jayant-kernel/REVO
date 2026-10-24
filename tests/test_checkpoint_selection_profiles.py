"""Explicit business profiles earn evidence via typed SQL, real replay and runtime."""
from collections import Counter

import pytest
from pydantic import TypeAdapter, ValidationError

from scripts.engineering_qualification_receipts import profile
from scripts.phase3_diagnostic import _reference_sql
from tests.test_stage2_receipt_producer import assert_receipt
from tests.test_stage5_sla_profile import matches
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.metamorphic import contract_relation_tables
from verified_data_factory.verification.public_rule_proofs import public_proofs
from verified_data_factory.verification.qualification import exists_profile as exists
from verified_data_factory.verification.qualification import final_leg_profile as final_leg
from verified_data_factory.verification.qualification import grade_revisions_profile as grade
from verified_data_factory.verification.qualification import inventory_flow_profile as inventory
from verified_data_factory.verification.qualification import paid_invoices_profile as paid
from verified_data_factory.verification.qualification import previous_play_profile as previous
from verified_data_factory.verification.qualification import (
    reconciliation_profile as reconciliation,
)
from verified_data_factory.verification.qualification import repeat_payment_profile as retention
from verified_data_factory.verification.qualification import required_courses_profile as required
from verified_data_factory.verification.qualification import support_breaches_profile as support
from verified_data_factory.verification.qualification import throughput_profile as throughput
from verified_data_factory.verification.qualification import weekly_visits_profile as weekly
from verified_data_factory.verification.receipt_observations import (
    observation_fixture,
    observed_behaviors,
)

pytest_plugins = ["tests.test_stage2_receipt_producer"]
PROFILES = [(paid.CONTRACT, 1, paid), (exists.CONTRACT, 2, exists), (final_leg.CONTRACT, 1, final_leg),
            (weekly.CONTRACT, 1, weekly), (retention.CONTRACT, 1, retention),
            (reconciliation.CONTRACT, 1, reconciliation), (previous.CONTRACT, 1, previous),
            (support.CONTRACT, 1, support), (grade.CONTRACT, 2, grade), (throughput.CONTRACT, 2, throughput),
            (required.CONTRACT, 1, required), (inventory.CONTRACT, 2, inventory)]


@pytest.mark.parametrize("contract,version,module", PROFILES)
def test_meaningful_failures_and_correct_formulations(contract, version, module):
    task = generate_task(load_builtin_registry().get(contract, version), 94001)
    reference = _reference_sql()[contract]
    failures = module.failures(reference)
    assert len(failures) >= 20 and len(set(failures.values())) == len(failures)
    formulations = module.alternatives(reference)
    assert len(set(formulations)) == 3
    for label, wrong in failures.items():
        assert wrong != reference, label
        assert not matches(task, wrong, module.rich_fixture()), label
    for correct in formulations:
        assert matches(task, correct, module.rich_fixture())
        assert matches(task, correct, {name: [] for name in task.tables})
    canonical, proofs = public_proofs(task)
    assert canonical == reference
    authority = public_behavior_map(task)
    assert authority.granular and authority.task_matches_public_contract
    for rule in authority.rules:
        if rule.kind == "semantic":
            proof = proofs[rule.proof_key]
            assert matches(task, reference, proof["witness"]), rule.rule_id
            assert not matches(task, proof["wrong_sql"], proof["witness"]), rule.rule_id


@pytest.mark.parametrize("contract,version,module", PROFILES)
def test_real_rules_mutations_nullable_domains_and_relation_replay(producer_root, contract, version, module):
    from scripts.engineering_receipt_artifacts import ArtifactWriter

    writer = ArtifactWriter(producer_root, "selection-profile-proof", contract, version, ["pyproject.toml"])
    reference = _reference_sql()[contract]
    rules = writer.rules()
    assert_receipt(writer, "rules", rules)
    data = assert_receipt(writer, "mutation", writer.mutations(rules))
    assert data["metrics"]["valid_non_equivalent"] >= 3
    assert_receipt(writer, "relations", writer.relations(reference, module.relation_specs(reference)))
    assert_receipt(writer, "fixture_diversity", writer.diversity())
    if contract == exists.CONTRACT:
        country = next(rule for rule in rules.rules if rule.rule_id == "schema:customers.country")
        assert country.disposition == "DOMAIN_CONFORMANCE"


@pytest.mark.parametrize("contract,version,module", PROFILES)
def test_full_selection_fuzz_is_900_cases_with_three_executed_formulations(producer_root, contract, version, module):
    from scripts.engineering_receipt_artifacts import ArtifactWriter

    writer = ArtifactWriter(producer_root, "selection-full-fuzz", contract, version, ["pyproject.toml"])
    detail = writer.fuzz(module.alternatives(_reference_sql()[contract]))
    data = assert_receipt(writer, "fuzz", detail)
    assert len(detail.cases) == 900 and data["checks_run"] == 2700
    assert data["metrics"]["divergences"] == 0
    assert all(min(counts.values()) >= 20 for counts in detail.observed_counts.values())


@pytest.mark.parametrize("contract,version,module", PROFILES)
def test_observations_are_content_measured_and_seed_campaigns_are_nonvacuous(contract, version, module):
    from verified_data_factory.verification.receipt_models import FuzzDetail

    adapter = TypeAdapter(FuzzDetail.model_fields["observation_policy"].annotation)
    adapter.validate_python(observed_behaviors(contract, version, module.rich_fixture())[0])
    with pytest.raises(ValidationError):
        adapter.validate_python("unsupported-observed-policy")
    empty = {name: [] for name in module.rich_fixture()}
    assert observed_behaviors(contract, version, empty)[2] == set()
    for seed in (1, 43, 94001):
        counts = Counter()
        contents = set()
        for index in range(300):
            tables = observation_fixture(contract, version, seed, index)
            _, required, observed = observed_behaviors(contract, version, tables)
            counts.update(observed)
            contents.add(str(tables))
        assert len(contents) == 300
        assert all(counts[label] >= 20 for label in required)


@pytest.mark.parametrize("contract,wrong_version", [(paid.CONTRACT, 2), (exists.CONTRACT, 1),
                                                    (inventory.CONTRACT, 1),
                                                    ("sql.aggregation.manufacturing_line_scrap", 2),
                                                   ("sql.funnel.saas_activation_payment", 1)])
def test_dispatch_never_borrows_another_contract_or_version(tmp_path, contract, wrong_version):
    with pytest.raises(ValueError, match="unsupported qualification profile"):
        profile(tmp_path, contract, wrong_version)


@pytest.mark.parametrize("contract,version,module", PROFILES)
def test_relation_ids_do_not_cross_contract_versions(contract, version, module):
    task = generate_task(load_builtin_registry().get(contract, version), 94001)
    for relation, _, tables in module.relation_specs(_reference_sql()[contract]):
        transformed, reason = contract_relation_tables(task, tables, relation)
        assert transformed is not None and reason
        other = generate_task(load_builtin_registry().get(
            exists.CONTRACT if contract == paid.CONTRACT else paid.CONTRACT, 2 if contract == paid.CONTRACT else 1), 94001)
        assert contract_relation_tables(other, other.tables, relation)[0] is None
