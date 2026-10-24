"""Reject apparent fixture diversity produced solely by row shuffling."""
import json
from pathlib import Path

import pytest

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.hidden_fixtures import fixture_fingerprint
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.hidden import derive_hidden_seed
from verified_data_factory.verification.models import VERIFICATION_CONFIG_VERSION
from verified_data_factory.verification.oracle_registry import get_oracle


def latest_contracts():
    latest = {}
    for template in load_builtin_registry().list():
        if template.template_id not in latest or latest[template.template_id].version < template.version:
            latest[template.template_id] = template
    return sorted((t.template_id, t.version) for t in latest.values())


@pytest.mark.parametrize("contract,version", latest_contracts())
def test_hidden_databases_have_four_distinct_contents(contract, version):
    rubric = json.loads(Path("configs/package_a/engineering-rubric.json").read_text())
    task = generate_task(load_builtin_registry().get(contract, version), 1)
    backend = DerivedTaskBackend()
    hashes = {fixture_fingerprint(task, task.tables)}
    for index in range(3):
        seed = derive_hidden_seed(task.seed, VERIFICATION_CONFIG_VERSION, index)
        hashes.add(fixture_fingerprint(task, backend.hidden_tables(task, seed)))
    assert len(hashes) >= rubric["thresholds"]["minimum_distinct_fixtures_including_original"]


def test_fixture_fingerprint_ignores_only_row_order():
    task = generate_task(load_builtin_registry().get("sql.funnel.saas_activation_payment", 2), 1)
    shuffled = {name: list(reversed(rows)) for name, rows in task.tables.items()}
    assert fixture_fingerprint(task, shuffled) == fixture_fingerprint(task, task.tables)


def test_hidden_transform_uses_bound_metadata_without_reloading_registry(monkeypatch):
    import verified_data_factory.task_engine.registry as registry_module
    from verified_data_factory.task_engine.hidden_fixtures import diverse_hidden_tables
    task = generate_task(load_builtin_registry().get("sql.funnel.saas_activation_payment", 2), 1)
    def unexpected_reload(*args, **kwargs):
        raise AssertionError("redundant registry reload during bound-task transformation")
    monkeypatch.setattr(registry_module, "load_builtin_registry", unexpected_reload)
    tables = diverse_hidden_tables(task, 43, 2)
    assert len(tables["account_funnel"]) == 2 * len(task.tables["account_funnel"])


def test_repeated_fixture_provider_cannot_pass_the_diversity_gate():
    from tests.verify_testkit import SimBackend, make_candidate
    from verified_data_factory.verification.hidden import run_hidden_checks
    from verified_data_factory.verification.models import ComparisonPolicy

    class RepeatedBackend(SimBackend):
        def hidden_tables(self, task, hidden_seed):
            return task.tables

    task = generate_task(load_builtin_registry().get("sql.funnel.saas_activation_payment", 2), 1)
    candidate = make_candidate(task, "SELECT 1")
    seeds = [derive_hidden_seed(task.seed, VERIFICATION_CONFIG_VERSION, i) for i in range(3)]
    outcome = run_hidden_checks(task, candidate, get_oracle(task.template_id, task.template_version).fn,
                                RepeatedBackend(), seeds, ComparisonPolicy())
    assert outcome.inconclusive > 0
    assert outcome.distinct_fixtures == 1
    assert outcome.minimum_distinct_fixtures == 4
    assert any(case.failure_code == "WEAK_SUITE" for case in outcome.cases)


@pytest.mark.parametrize("contract,version", [("sql.funnel.saas_activation_payment", 2), ("sql.funnel.logistics_parcel_delivery", 2)])
def test_ledger_variants_preserve_entity_guarantees_and_vary_cardinality(contract, version):
    task = generate_task(load_builtin_registry().get(contract, version), 1)
    backend = DerivedTaskBackend()
    counts = []
    for index in range(3):
        seed = derive_hidden_seed(task.seed, VERIFICATION_CONFIG_VERSION, index)
        tables = backend.hidden_tables(task, seed)
        rows = next(iter(tables.values()))
        counts.append(len(rows))
        entities = {}
        for row in rows:
            entities.setdefault(row["entity_id"], []).append(row)
        for members in entities.values():
            assert len({r["group_key"] for r in members}) == 1
            keys = [(r["occurred_at"], r["sequence"]) for r in members]
            assert len(keys) == len(set(keys))
        get_oracle(contract, version).fn(task.requirements, tables)
    assert len(set(counts)) == 3
