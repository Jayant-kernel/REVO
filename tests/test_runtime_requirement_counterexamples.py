"""Qualification clause fixtures must discriminate in the normal candidate path."""
import pytest

from scripts.engineering_campaign import ROOT
from scripts.engineering_qualification_receipts import profile
from scripts.engineering_receipt_artifacts import SUPPORTED
from tests.test_stage5_sla_profile import matches
from verified_data_factory.sandbox import load_config
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.backend import DerivedTaskBackend


@pytest.mark.parametrize("contract,version", sorted(SUPPORTED))
def test_runtime_clause_fixtures_cover_every_required_wrong_query(contract, version):
    task = generate_task(load_builtin_registry().get(contract, version), 94001)
    backend = DerivedTaskBackend(load_config("configs/sandbox_production.yaml"))
    fixtures = backend.requirement_counterexample_tables(task)
    correct, wrong, _ = profile(ROOT, contract, version)
    assert fixtures
    for sql in correct:
        assert all(matches(task, sql, tables) for tables in fixtures)
    for sql, _ in wrong:
        assert any(not matches(task, sql, tables) for tables in fixtures), sql
