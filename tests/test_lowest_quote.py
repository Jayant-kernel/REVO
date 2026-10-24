"""Lowest quote raw-domain, typed SQL and actual-candidate regression proofs."""
import pytest

from scripts.engineering_qualification_receipts import profile
from scripts.engineering_receipt_artifacts import SUPPORTED
from scripts.phase3_diagnostic import _reference_sql
from tests.test_stage5_sla_profile import matches
from verified_data_factory.sandbox.policy import check_policy
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.errors import FixtureError, ValidationError
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.task_engine.hidden_fixtures import (
    diverse_hidden_tables,
    fixture_fingerprint,
)
from verified_data_factory.task_engine.validation import validate_task
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.qualification.lowest_quote_candidate_transforms import (
    candidate_proofs,
    prototypes,
)
from verified_data_factory.verification.qualification.lowest_quote_profile import (
    BEHAVIORS,
    CONTRACT,
    REFERENCE,
    alternatives,
    challenge_specs,
    expected,
    fixture,
    observed,
    proofs,
    quote,
    rich_fixture,
)

pytest_plugins = ["tests.test_stage2_receipt_producer"]


def test_fuzz_policy_and_required_behavior_counts_match_frozen_campaign():
    from collections import Counter

    from pydantic import TypeAdapter

    from verified_data_factory.verification.receipt_models import FuzzDetail

    validator = TypeAdapter(FuzzDetail.model_fields["observation_policy"].annotation)
    for seed in (1, 43, 94001):
        counts = Counter()
        for index in range(300):
            policy, required, found = observed(fixture(seed, index))
            assert validator.validate_python(policy) == "lowest-quote-observed-v1"
            counts.update(found)
        assert all(counts[name] >= 20 for name in required), counts


@pytest.fixture
def task():
    return generate_task(load_builtin_registry().get(CONTRACT, 1), 94001)


def test_registry_profile_and_full_granular_map(task):
    assert (CONTRACT, 1) in SUPPORTED
    assert _reference_sql()[CONTRACT] == REFERENCE
    correct, wrong, relations = profile(None, CONTRACT, 1)
    assert len(correct) == 3 and len(wrong) >= 20 and len(relations) == 2
    authority = public_behavior_map(task)
    assert authority.granular and authority.task_matches_public_contract
    public = proofs(REFERENCE)
    assert all(rule.proof_key in public or rule.proof_key == "schema" for rule in authority.rules)


@pytest.mark.parametrize("column,value", [("price_cents", v) for v in (-1, 2147483648, True, False, "10", 1.5)] +
                         [(c, v) for c in ("part", "supplier") for v in (None, 1, True)])
def test_raw_domain_rejected_before_coercion(task, column, value):
    tables = {"quotes": [{**quote(), column: value}]}
    with pytest.raises(ValueError, match="quotes\\."):
        expected(task.requirements, tables)
    with pytest.raises(FixtureError):
        materialize_duckdb(task.schema_, tables)
    changed = task.model_copy(update={"tables": tables, "fixture_metadata": task.fixture_metadata.model_copy(update={
        "tables": {"quotes": task.fixture_metadata.tables["quotes"].model_copy(update={"row_count": 1})}})})
    with pytest.raises(ValidationError):
        validate_task(changed)


def test_empty_null_tie_repeat_binary_and_boundaries(task):
    assert expected({}, {"quotes": []}).rows == []
    assert expected({}, {"quotes": [quote(price=None)]}).rows == []
    assert expected({}, rich_fixture()).rows == [
        ["", "", 0], ["P", "s", 12], ["case", "Z", 8], ["max", "s", 2147483647],
        ["p", "B", 10], ["p ", " s ", 11], ["unicode", "z", 7]]
    for tables in ({"quotes": []}, {"quotes": [quote(price=None)]}, rich_fixture()):
        assert all(matches(task, sql, tables) for sql in alternatives(REFERENCE))


def test_seeded_material_diversity_observed_not_labelled(task):
    frames = [fixture(seed, index) for seed, index in ((1, 0), (43, 1), (94001, 2), (1, 12))]
    assert fixture(43, 1) == frames[1]
    assert len({fixture_fingerprint(task, tables) for tables in frames}) == 4
    found = set().union(*(observed(tables)[2] for tables in frames))
    assert found == set(BEHAVIORS)
    assert diverse_hidden_tables(task, 43, 1) == frames[1]
    for tables in frames:
        assert all(matches(task, sql, tables) for sql in alternatives(REFERENCE))


def test_every_public_semantic_and_domain_witness(task):
    for key, proof in proofs(REFERENCE).items():
        if "wrong_sql" in proof:
            assert check_policy(proof["wrong_sql"]).allowed, key
            assert matches(task, REFERENCE, proof["witness"]), key
            assert not matches(task, proof["wrong_sql"], proof["witness"]), key
        else:
            with pytest.raises(ValueError):
                expected({}, proof["witness"])


def test_twenty_distinct_executable_wrong_forms(task):
    challenges = challenge_specs(REFERENCE)
    assert len({sql for sql, _ in challenges}) >= 20
    for sql, tables in challenges:
        assert check_policy(sql).allowed
        assert not matches(task, sql, tables), sql


@pytest.mark.parametrize("sql", prototypes())
def test_actual_ast_candidate_transformations_execute(task, sql):
    public = proofs(REFERENCE)
    derived = candidate_proofs(sql, REFERENCE, public)
    assert derived is not None and set(derived) == set(public)
    for key, proof in derived.items():
        if "wrong_sql" in proof:
            assert check_policy(proof["wrong_sql"]).allowed, key
            assert matches(task, sql, proof["witness"]), key
            assert not matches(task, proof["wrong_sql"], proof["witness"]), key


def test_aliases_formatting_and_unsupported_abstention(task):
    sql = alternatives(REFERENCE)[1].replace("q.", "actual.").replace("quotes q", "quotes actual")
    assert candidate_proofs(sql, REFERENCE, proofs(REFERENCE)) is not None
    for unsupported in (REFERENCE + " LIMIT 1", REFERENCE.replace("= 1", "<= 2"),
                         REFERENCE.replace("supplier ASC", "supplier DESC"), "SELECT * FROM quotes",
                         prototypes()[-1].replace("MIN(price_cents)", "MAX(price_cents)"),
                         prototypes()[-1].replace("MIN(price_cents) OVER (PARTITION BY part)",
                                                   "MIN(price_cents) OVER (PARTITION BY supplier)")):
        assert candidate_proofs(unsupported, REFERENCE, proofs(REFERENCE)) is None
    assert matches(task, sql, rich_fixture())


def test_relation_discriminators(task):
    from verified_data_factory.verification.metamorphic import contract_relation_tables
    from verified_data_factory.verification.qualification.lowest_quote_profile import relation_specs

    for relation, wrong, before in relation_specs(REFERENCE):
        after, reason = contract_relation_tables(task, before, relation)
        assert after is not None, reason
        assert expected({}, before).rows == expected({}, after).rows
        assert matches(task, REFERENCE, after)
        assert matches(task, wrong, before)
        assert not matches(task, wrong, after)


@pytest.mark.parametrize("sql", prototypes()[1:])
def test_runtime_actual_candidate_earns_coverage(task, sql):
    from tests.verify_testkit import make_candidate
    from verified_data_factory.sandbox import SandboxExecutor, load_config
    from verified_data_factory.verification import verify_candidate
    from verified_data_factory.verification.backend import DerivedTaskBackend

    config = load_config("configs/sandbox_production.yaml")
    candidate = make_candidate(task, sql)
    execution = SandboxExecutor(config).execute(task, candidate)
    result = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(config))
    assert result.verdict == "PASS", result.summary
    assert result.verification_strength == "STRONG", result.model_dump_json()
    assert result.mutation.coverage_complete
    assert result.mutation.invalid == result.mutation.inconclusive == result.mutation.survived == 0
    assert all(d.candidate_execution_id and d.execution_id and d.retained_executions for d in result.mutation.details)


def test_unsupported_runtime_keeps_unknown_coverage(task):
    from tests.verify_testkit import make_candidate
    from verified_data_factory.sandbox import SandboxExecutor, load_config
    from verified_data_factory.verification import verify_candidate
    from verified_data_factory.verification.backend import DerivedTaskBackend

    sql = "SELECT part,MIN(supplier) AS supplier,MIN(price_cents) AS price_cents FROM (" + REFERENCE + ") chosen GROUP BY part ORDER BY part"
    config = load_config("configs/sandbox_production.yaml")
    candidate = make_candidate(task, sql)
    execution = SandboxExecutor(config).execute(task, candidate)
    result = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(config))
    assert result.verdict == "PASS", result.summary
    assert result.verification_strength != "STRONG"
    assert not result.mutation.coverage_complete


def test_small_rules_mutation_replay_without_collection_or_promotion(producer_root):
    from scripts.engineering_receipt_artifacts import ArtifactWriter
    from tests.test_stage2_receipt_producer import assert_receipt

    writer = ArtifactWriter(producer_root, "lowest-quote-unit-rules", CONTRACT, 1, ["pyproject.toml"])
    rules = writer.rules()
    assert_receipt(writer, "rules", rules)
    assert_receipt(writer, "mutation", writer.mutations(rules))
