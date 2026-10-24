"""Integrated task/proof/runtime coverage; authored tests are not model records."""
import pytest

from scripts.engineering_qualification_receipts import profile
from scripts.engineering_receipt_artifacts import ArtifactWriter
from tests.test_stage5_sla_profile import matches
from tests.verify_testkit import make_candidate
from verified_data_factory.sandbox import SandboxExecutor, load_config
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.errors import FixtureError
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.task_engine.hidden_fixtures import (
    diverse_hidden_tables,
    fixture_fingerprint,
)
from verified_data_factory.verification import verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.qualification.delivery_profiles import (
    PROFILE_IDS,
    get_profile,
)
from verified_data_factory.verification.qualification.structural import structural_checks
from verified_data_factory.verification.receipt_observations import observed_behaviors

pytest_plugins = ["tests.test_stage2_receipt_producer"]


@pytest.mark.parametrize("pair", sorted(PROFILE_IDS))
def test_public_profile_dispatch_and_rule_mutation_receipts(producer_root, pair):
    task = generate_task(load_builtin_registry().get(*pair), 94001)
    module = get_profile(*pair)
    assert module is not None
    authority = public_behavior_map(task)
    assert authority.granular and authority.task_matches_public_contract
    correct, wrong, relations = profile(producer_root, *pair)
    assert len(correct) == 3 and len(wrong) >= 20 and len(relations) == 2
    frames = [task.tables, *(diverse_hidden_tables(task, seed, index) for index, seed in enumerate((1, 43, 94001), 1))]
    assert len({fixture_fingerprint(task, tables) for tables in frames}) == 4
    for tables in frames:
        module.validate_rows(tables)
        assert observed_behaviors(*pair, tables)[0] in {"language-titles-observed-v1", "pareto-shipping-observed-v1", "renewal-coverage-observed-v1", "queue-batches-observed-v1"}
    writer = ArtifactWriter(producer_root, "delivery-unit-" + pair[0], *pair, ["pyproject.toml"])
    rules = writer.rules()
    writer.receipt("rules", rules)
    writer.receipt("mutation", writer.mutations(rules))
    writer.receipt("relations", writer.relations(correct[0], relations))


@pytest.mark.parametrize("pair", sorted(PROFILE_IDS))
def test_actual_noncanonical_alias_candidate_runtime(pair):
    task = generate_task(load_builtin_registry().get(*pair), 94001)
    module = get_profile(*pair)
    assert module is not None
    if task.family == "simple_joins":
        sql = module.REFERENCE.replace("r.", "requested.").replace("requests r", "requests requested")
    elif task.template_id == "sql.retention.renewal_coverage":
        sql = module.REFERENCE.replace("e.", "actual.").replace("episodes e", "episodes actual")
    elif task.template_id == "sql.windows.queue_batches":
        sql = module.alternatives(module.REFERENCE)[2].replace("s.", "src.").replace("submissions s", "submissions src")
    else:
        sql = module.REFERENCE.replace("o.", "offered.").replace("options o", "options offered")
    candidate = make_candidate(task, sql)
    config = load_config("configs/sandbox_production.yaml")
    execution = SandboxExecutor(config).execute(task, candidate)
    result = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(config))
    assert result.verdict == "PASS", result.model_dump_json()
    assert result.verification_strength == "STRONG", result.model_dump_json()
    assert result.mutation.coverage_complete and result.mutation.mutation_score == 1.0
    assert result.mutation.invalid == result.mutation.inconclusive == result.mutation.survived == 0


@pytest.mark.parametrize("pair", sorted(PROFILE_IDS))
def test_materializer_rejects_raw_integer_bool_before_coercion(pair):
    task = generate_task(load_builtin_registry().get(*pair), 94001)
    module = get_profile(*pair)
    assert module is not None
    tables = module.rich_fixture()
    if task.family == "simple_joins":
        tables["requests"][0]["request_id"] = True
    elif task.template_id == "sql.retention.renewal_coverage":
        tables["episodes"][0]["episode_id"] = True
    elif task.template_id == "sql.windows.queue_batches":
        tables["submissions"][0]["submission_id"] = True
    else:
        tables["options"][0]["option_id"] = True
    with pytest.raises(FixtureError):
        materialize_duckdb(task.schema_, tables)


def test_equivalent_pareto_count_control_is_structural_failure_not_semantic_kill():
    pair = ("sql.subqueries.pareto_shipping", 1)
    task = generate_task(load_builtin_registry().get(*pair), 94001)
    module = get_profile(*pair)
    assert module is not None
    sql = module.structural_controls()["count_dominator"]
    assert structural_checks(task, module.REFERENCE)["status"] == "PASS"
    assert structural_checks(task, sql)["status"] == "FAIL"
    candidate = make_candidate(task, sql)
    config = load_config("configs/sandbox_production.yaml")
    execution = SandboxExecutor(config).execute(task, candidate)
    result = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(config))
    assert matches(task, sql, task.tables)
    assert result.verdict == "FAIL"
    assert result.mutation is None


def test_unaliased_correlated_pareto_is_inconclusive_not_false_structure_failure():
    pair = ("sql.subqueries.pareto_shipping", 1)
    task = generate_task(load_builtin_registry().get(*pair), 94001)
    module = get_profile(*pair)
    assert module is not None
    sql = module.REFERENCE.replace("FROM options o ", "FROM options ").replace("o.", "options.")
    assert matches(task, sql, task.tables)
    assert structural_checks(task, sql)["status"] == "INCONCLUSIVE"
    candidate = make_candidate(task, sql)
    config = load_config("configs/sandbox_production.yaml")
    execution = SandboxExecutor(config).execute(task, candidate)
    result = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(config))
    assert result.verdict == "INCONCLUSIVE"
    assert result.verification_strength != "STRONG"
