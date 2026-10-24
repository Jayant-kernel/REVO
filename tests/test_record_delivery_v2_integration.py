"""Bounded v2 integration evidence; no qualification or model record emission."""
import pytest

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.qualification.delivery_profiles import get_profile
from verified_data_factory.verification.qualification.public_rule_proofs import (
    public_proofs,
    schema_checks,
)
from verified_data_factory.verification.qualification.structural import structural_checks


@pytest.mark.parametrize("contract", ["sql.retention.renewal_coverage", "sql.windows.queue_batches"])
def test_public_map_all_proof_keys_raw_schema_and_exact_version(contract):
    task = generate_task(load_builtin_registry().get(contract, 1), 94001)
    module = get_profile(contract, 1)
    assert module is not None and get_profile(contract, 2) is None
    authority = public_behavior_map(task)
    _, proofs = public_proofs(task)
    assert authority.task_matches_public_contract and authority.granular
    assert {r.proof_key for r in authority.rules} - {"schema"} <= proofs.keys()
    for table in task.schema_:
        for column in table.columns:
            checks = schema_checks(task, table.name, column.name)
            assert checks["raw_rejections"] and checks["raw_conformance"]


def test_queue_structure_equivalent_control_and_unknown():
    module = get_profile("sql.windows.queue_batches", 1)
    task = generate_task(load_builtin_registry().get(module.CONTRACT, 1), 94001)
    assert structural_checks(task, module.REFERENCE)["status"] == "PASS"
    assert structural_checks(task, module.structural_control())["status"] == "FAIL"
    assert structural_checks(task, module.REFERENCE.replace("NTILE(3)", "NTILE(1+2)"))["status"] == "INCONCLUSIVE"
