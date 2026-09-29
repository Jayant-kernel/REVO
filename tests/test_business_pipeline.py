"""End-to-end Phase 8 validation (§75).

Snapshot → training release → private benchmark → experiment →
baseline/treatment → comparison → economics → customer fixture →
business report, built twice with identical content identities.
"""

import json

from tests.business_fixtures import (
    FIXTURE_NOTE,
    baseline_outcomes,
    benchmark_items,
    contaminated_training_context,
    control_outcomes,
    frozen_fixture_benchmark,
    training_context,
    treatment_outcomes,
)
from verified_data_factory.business import (
    ArmSpec,
    ArtifactAdapter,
    BusinessClaim,
    HypothesisCriteria,
    build_business_report,
    build_comparison,
    build_cost_model,
    check_contamination,
    compute_economics,
    create_benchmark,
    create_experiment,
    create_pilot,
    freeze_benchmark,
    record_customer_validation,
    record_evidence,
    report_content_id,
    report_to_json,
    run_experiment,
    validate_benchmark,
    validate_claims,
)


def _outcome_files(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    for arm, outcomes in (
        ("baseline", baseline_outcomes()),
        ("control", control_outcomes()),
        ("treatment", treatment_outcomes()),
    ):
        (tmp_path / f"{arm}.jsonl").write_text(
            "\n".join(json.dumps(o.model_dump(mode="json")) for o in outcomes) + "\n",
            encoding="utf-8",
        )


def _pipeline(tmp_path, run_tag):
    # Training release reference (Phase 7 manifest shape, referenced not rebuilt).
    manifest = {
        "release_id": "sha256:" + "ab" * 32,
        "dataset_snapshot_id": "sha256:" + "cd" * 32,
        "product_type": "TRAIN",
        "visibility": "INTERNAL",
        "record_count": 35,
    }
    # Private benchmark from explicit items, frozen.
    definition, items = create_benchmark(
        items=benchmark_items(),
        benchmark_version="1.0",
        split="private_benchmark",
        evaluation_policy="owner-harness-execution",
        scoring_policy="aggregation-v1",
        privacy_level="PRIVATE",
        dataset_release_id=manifest["dataset_snapshot_id"],
    )
    definition = freeze_benchmark(definition)
    assert validate_benchmark(definition, items) == []
    # Contamination vs training context must be clean.
    ids, groups = training_context()
    contamination = check_contamination(
        benchmark_id=definition.benchmark_id,
        benchmark_items=items,
        training_record_ids=ids,
        training_groups=groups,
    )
    assert contamination.is_clean is True
    # Experiment definition + both arms.
    _outcome_files(tmp_path)
    config = create_experiment(
        benchmark_id=definition.benchmark_id,
        baseline=ArmSpec(model="fixture-base", adaptation_method="NONE"),
        treatment=ArmSpec(
            model="fixture-base",
            dataset_release_id=manifest["release_id"],
            adaptation_method="SFT",
        ),
        experiment_version="1.0",
        scoring_method="external-harness-aggregation",
        seeds=[42],
    )
    criteria = HypothesisCriteria(
        primary_metric="execution_accuracy",
        improvement_threshold_pp=5.0,
        minimum_benchmark_size=10,
    )
    result = run_experiment(
        config=config,
        adapter=ArtifactAdapter(),
        locator=str(tmp_path),
        run_id=run_tag,
        criteria=criteria,
    )
    comparison = build_comparison(
        experiment_id=config.experiment_id,
        baseline=result.baseline_metrics,
        treatment=result.treatment_metrics,
        stats=result.statistical_evidence,
        criteria=criteria,
    )
    # Economics from measured-style inputs.
    economics = compute_economics(
        build_cost_model(
            variable_costs={"inference": 120.0, "execution_cpu": 30.0},
            fixed_costs={"storage": 50.0},
            assumptions=["e2e fixture"],
            measured=False,
        ),
        100,
    )
    # Customer fixture (USER_REPORTED, no purchase claims).
    validation = record_customer_validation(
        validation_id="v-e2e",
        organization="Fixture Labs",
        segment="AI evaluation companies",
        contact_role="eval lead",
        use_case="Model evaluation datasets",
        feedback="PRODUCT_USEFUL",
        willingness_signal="DATASET_TESTED",
        evidence_type="USER_REPORTED",
        evidence_reference="notes/v-e2e",
    )
    pilot = create_pilot(
        pilot_id="p-e2e",
        product_release_id=manifest["release_id"],
        customer_segment="AI evaluation companies",
    )
    measured = record_evidence(
        evidence_id="ev-e2e",
        evidence_type="benchmark_score",
        claim="treatment beats baseline by 25pp on the frozen benchmark",
        value=25.0,
        unit="percentage-points",
        source="fixture harness",
        experiment_id=config.experiment_id,
        benchmark_id=definition.benchmark_id,
        dataset_release_id=manifest["release_id"],
        status="MEASURED",
        notes=FIXTURE_NOTE,
    )
    claim = BusinessClaim(
        claim_id="claim-e2e",
        statement="Treatment beats baseline by 25pp.",
        claim_type="PERFORMANCE",
        evidence_ids=["ev-e2e"],
        status="MEASURED",
        metric="execution_accuracy",
        asserted_delta_pp=25.0,
    )
    verdicts = validate_claims([claim], [measured], [comparison])
    assert verdicts["claim-e2e"][0] == "CLAIM_SUPPORTED"
    report = build_business_report(
        report_id="r-e2e",
        release_manifests=[{**manifest, "output_format": "jsonl", "families": ["cte"]}],
        comparisons=[comparison],
        results=[result],
        validations=[validation],
        evidence=[measured],
        claims=[claim],
        economics=economics,
        hypothesis_verdict=comparison.verdict,
        hypothesis_detail="e2e fixture verdict",
    )
    _ = pilot
    return {
        "benchmark_id": definition.benchmark_id,
        "experiment_id": config.experiment_id,
        "config": config.model_dump(mode="json"),
        "report_content": report_content_id(report),
        "report_json": report_to_json(report),
        "verdict": comparison.verdict,
    }


def test_end_to_end_twice_identical(tmp_path):
    first = _pipeline(tmp_path / "a", "run-1")
    second = _pipeline(tmp_path / "b", "run-2")
    assert first["benchmark_id"] == second["benchmark_id"]
    assert first["experiment_id"] == second["experiment_id"]
    assert first["config"] == second["config"]
    assert first["report_content"] == second["report_content"]
    assert first["verdict"] == "HYPOTHESIS_SUPPORTED"
    # Operational run ids differ between the two builds but never enter
    # content identities (asserted equal above).


def test_contaminated_context_blocks_clean_claim():
    _, items = frozen_fixture_benchmark()
    ids, groups = contaminated_training_context()
    report = check_contamination(
        benchmark_id="b",
        benchmark_items=items,
        training_record_ids=ids,
        training_groups=groups,
    )
    assert report.is_clean is False
