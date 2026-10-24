"""Result-equivalent missing HAVING is structural failure, never a semantic kill."""
from scripts.engineering_receipt_artifacts import ArtifactWriter
from scripts.phase3_diagnostic import _reference_sql
from tests.test_stage2_receipt_producer import assert_receipt
from tests.test_stage5_sla_profile import matches
from tests.verify_testkit import make_candidate
from verified_data_factory.sandbox import SandboxExecutor, load_config
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification import verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.qualification import throughput_profile as throughput
from verified_data_factory.verification.qualification.structural import structural_checks

pytest_plugins = ["tests.test_stage2_receipt_producer"]


def test_having_structure_and_threshold_semantics_are_distinct():
    task = generate_task(load_builtin_registry().get(throughput.CONTRACT,2),94001)
    reference = _reference_sql()[throughput.CONTRACT]
    for sql in throughput.alternatives(reference):
        assert structural_checks(task,sql)["status"] == "PASS"
        assert matches(task,sql,throughput.rich_fixture())
    equivalent = throughput.equivalent_without_having()
    assert matches(task,equivalent,throughput.rich_fixture())
    assert structural_checks(task,equivalent)["status"] == "FAIL"
    decorative = ("WITH totals AS (SELECT warehouse,SUM(units) AS total_units FROM warehouse_loads "
        "WHERE status='posted' AND EXTRACT(YEAR FROM loaded_on)=2025 GROUP BY warehouse HAVING SUM(units) IS NOT NULL) "
        "SELECT warehouse,total_units FROM totals WHERE total_units>=40 ORDER BY warehouse")
    assert matches(task,decorative,throughput.rich_fixture())
    assert structural_checks(task,decorative)["status"] == "FAIL"


def test_structural_receipt_retains_equal_results_and_excludes_semantic_mutation_count(producer_root):
    writer = ArtifactWriter(producer_root,"throughput-structure",throughput.CONTRACT,2,["pyproject.toml"])
    rules = writer.rules()
    structural = [rule for rule in rules.rules if rule.kind == "structural"]
    assert len(structural) == 1
    assert structural[0].correct.outcome == structural[0].wrong.outcome == "MATCH"
    receipt = assert_receipt(writer,"rules",rules)
    assert receipt["metrics"]["structural_rules"] == 1
    mutations = writer.mutations(rules)
    assert structural[0].rule_id not in mutations.required_rules
    assert all(structural[0].rule_id not in mutant.rule_ids for mutant in mutations.mutants)
    assert_receipt(writer,"mutation",mutations)


def test_actual_missing_having_fails_before_any_mutation_scoring(tmp_path):
    task = generate_task(load_builtin_registry().get(throughput.CONTRACT,2),94001)
    config = load_config("configs/sandbox_production.yaml")
    candidate = make_candidate(task,throughput.equivalent_without_having())
    execution = SandboxExecutor(config).execute(task,candidate)
    assert execution.status == "SUCCEEDED"
    result = verify_candidate(task,candidate,execution,backend=DerivedTaskBackend(config))
    (tmp_path/"structural-runtime.json").write_text(result.model_dump_json(indent=2))
    assert result.verdict == "FAIL" and result.failure_code == "STRUCTURAL_REQUIREMENT_FAILED"
    assert result.mutation is None
    assert result.evidence["structural_requirements"]["status"] == "FAIL"
