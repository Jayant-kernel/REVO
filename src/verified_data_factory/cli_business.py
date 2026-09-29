"""Business CLI commands (Phase 8). Thin wrappers over business.api.

Benchmark items format (JSONL, one BenchmarkItem per line)::

    {"record_id": ..., "family": ..., "edge_cases": [...],
     "template_id": ..., "semantic_group": ..., "expected_sql": ...}

Outcomes layout (directory with one file per arm)::

    outcomes/baseline.jsonl outcomes/control.jsonl outcomes/treatment.jsonl

Each outcome line::

    {"record_id": ..., "correct": true, "family": ...,
     "edge_cases": [...], "latency_ms": 12.0, "error_type": null}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _read_json(path: str | Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc


def _read_jsonl(path: str | Path) -> list[Any]:
    rows = []
    with open(path, encoding="utf-8-sig") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except ValueError as exc:
                raise SystemExit(f"{path}:{lineno}: invalid JSON: {exc}") from exc
    return rows


def _write_json(path: str | Path, payload: Any) -> None:
    Path(path).write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )


def cmd_benchmark_create(args: argparse.Namespace) -> int:
    from verified_data_factory.business import BenchmarkItem, create_benchmark, freeze_benchmark

    items = [BenchmarkItem.model_validate(row) for row in _read_jsonl(args.items)]
    definition, _ = create_benchmark(
        items=items,
        benchmark_version=args.benchmark_version,
        split=args.split,
        evaluation_policy=args.evaluation_policy,
        scoring_policy=args.scoring_policy,
        privacy_level=args.privacy_level,
        dataset_release_id=args.dataset_release_id,
    )
    if args.freeze:
        definition = freeze_benchmark(definition)
    _write_json(args.output, definition.model_dump(mode="json"))
    print(f"benchmark={definition.benchmark_id} members={len(items)} frozen={definition.frozen}")
    return 0


def cmd_benchmark_validate(args: argparse.Namespace) -> int:
    from verified_data_factory.business import (
        benchmark_from_dict,
        benchmark_items_from_list,
        validate_benchmark,
    )

    definition = benchmark_from_dict(_read_json(args.benchmark))
    items = benchmark_items_from_list(_read_jsonl(args.items))
    violations = validate_benchmark(definition, items)
    for violation in violations:
        print(f"VIOLATION: {violation}", file=sys.stderr)
    print(f"violations={len(violations)} frozen={definition.frozen}")
    return 0 if not violations else 1


def cmd_benchmark_contamination(args: argparse.Namespace) -> int:
    from verified_data_factory.business import benchmark_items_from_list, check_contamination

    items = benchmark_items_from_list(_read_jsonl(args.items))
    training_ids = (
        [row["record_id"] for row in _read_jsonl(args.training_ids)] if args.training_ids else []
    )
    groups_list = _read_json(args.training_groups) if args.training_groups else []
    groups = {g["record_id"]: g for g in groups_list} if isinstance(groups_list, list) else {}
    report = check_contamination(
        benchmark_id=args.benchmark_id,
        benchmark_items=items,
        training_record_ids=training_ids,
        training_groups=groups,
    )
    print(
        f"clean={report.is_clean} exact={len(report.exact_overlap)} "
        f"structural={len(report.structural_overlap)} semantic={len(report.semantic_overlap)} "
        f"template={len(report.template_overlap)}"
    )
    if args.output:
        _write_json(args.output, report.model_dump(mode="json"))
    return 0 if report.is_clean else 1


def cmd_experiment_create(args: argparse.Namespace) -> int:
    from verified_data_factory.business import load_experiment_config

    config = load_experiment_config(args.config)
    _write_json(args.output, config.model_dump(mode="json"))
    print(f"experiment={config.experiment_id}")
    return 0


def cmd_experiment_run(args: argparse.Namespace) -> int:
    from verified_data_factory.business import (
        ArtifactAdapter,
        HypothesisCriteria,
        experiment_config_from_dict,
        run_experiment,
    )

    config = experiment_config_from_dict(_read_json(args.config))
    criteria = (
        HypothesisCriteria(
            primary_metric=args.primary_metric,
            improvement_threshold_pp=args.threshold_pp,
            minimum_benchmark_size=args.min_n,
        )
        if args.threshold_pp is not None
        else None
    )
    result = run_experiment(
        config=config,
        adapter=ArtifactAdapter(),
        locator=args.outcomes,
        run_id=args.run_id,
        failure_modes=args.failure_mode or [],
        criteria=criteria,
    )
    _write_json(args.output, result.model_dump(mode="json"))
    primary = next((d for d in result.deltas if d.metric == "execution_accuracy"), None)
    if primary is not None:
        print(f"delta_pp={primary.absolute_pp:.2f} n={primary.denominator_n}")
    print(f"result -> {args.output}")
    return 0


def cmd_experiment_compare(args: argparse.Namespace) -> int:
    from verified_data_factory.business import (
        ExperimentResult,
        HypothesisCriteria,
        compare_experiments,
    )

    result = ExperimentResult.model_validate(_read_json(args.result))
    criteria = (
        HypothesisCriteria(
            primary_metric=args.primary_metric,
            improvement_threshold_pp=args.threshold_pp,
            minimum_benchmark_size=args.min_n,
        )
        if args.threshold_pp is not None
        else None
    )
    comparison = compare_experiments(result, criteria)
    if args.output:
        _write_json(args.output, comparison.model_dump(mode="json"))
    for row in comparison.metrics:
        print(
            f"{row['metric']}: baseline={row['baseline']:.4f} "
            f"treatment={row['treatment']:.4f} delta_pp={row['absolute_pp']:.2f} n={row['denominator_n']}"
        )
    print(f"verdict={comparison.verdict}")
    return 0


def cmd_economics(args: argparse.Namespace) -> int:
    from verified_data_factory.business import build_cost_model, compute_economics, scenario_table

    payload = _read_json(args.costs) if args.costs else {}
    model = build_cost_model(
        variable_costs=payload.get("variable_costs"),
        fixed_costs=payload.get("fixed_costs"),
        assumptions=payload.get("assumptions", []),
        measured=bool(payload.get("measured", False)),
    )
    units = compute_economics(model, args.golden_records)
    print(
        f"total={units.total_cost} per_golden={units.cost_per_golden} unknown={units.unknown_inputs}"
    )
    if args.output:
        _write_json(
            args.output,
            {
                "unit_economics": units.model_dump(mode="json"),
                "scenarios": [
                    s.model_dump(mode="json")
                    for s in scenario_table(
                        payload.get("unit_variable"),
                        payload.get("fixed"),
                        payload.get("assumptions", []),
                    )
                ],
            },
        )
    return 0


def cmd_customer_record(args: argparse.Namespace) -> int:
    from verified_data_factory.business import record_customer_validation

    record = record_customer_validation(**_read_json(args.input))
    _write_json(args.output, record.model_dump(mode="json"))
    print(f"validation={record.validation_id} signal={record.willingness_signal}")
    return 0


def cmd_pilot_create(args: argparse.Namespace) -> int:
    from verified_data_factory.business import SuccessCriterion, create_pilot

    payload = _read_json(args.input)
    criteria = [SuccessCriterion.model_validate(c) for c in payload.get("success_criteria", [])]
    pilot = create_pilot(
        pilot_id=payload["pilot_id"],
        product_release_id=payload["product_release_id"],
        customer_segment=payload["customer_segment"],
        use_case=payload.get("use_case", ""),
        success_criteria=criteria,
        start_date=payload.get("start_date"),
    )
    _write_json(args.output, pilot.model_dump(mode="json"))
    print(f"pilot={pilot.pilot_id} status={pilot.status}")
    return 0


def cmd_pilot_transition(args: argparse.Namespace) -> int:
    from verified_data_factory.business import Pilot, transition_pilot

    pilot = Pilot.model_validate(_read_json(args.pilot))
    updated = transition_pilot(pilot, args.status, end_date=args.end_date)
    _write_json(args.output, updated.model_dump(mode="json"))
    print(f"pilot={updated.pilot_id} status={updated.status}")
    return 0


def cmd_pilot_evaluate(args: argparse.Namespace) -> int:
    from verified_data_factory.business import Pilot, evaluate_pilot

    pilot = Pilot.model_validate(_read_json(args.pilot))
    observed = _read_json(args.observed) if args.observed else {}
    updated = evaluate_pilot(pilot, {k: (None if v == "null" else v) for k, v in observed.items()})
    _write_json(args.output, updated.model_dump(mode="json"))
    for criterion in updated.success_criteria:
        print(f"{criterion.criterion_id}: {criterion.outcome}")
    return 0


def cmd_claims_validate(args: argparse.Namespace) -> int:
    from verified_data_factory.business import (
        BusinessClaim,
        BusinessEvidence,
        ExperimentComparison,
        validate_claims,
    )

    claims = [BusinessClaim.model_validate(c) for c in _read_json(args.claims)]
    evidence = [BusinessEvidence.model_validate(e) for e in _read_json(args.evidence)]
    comparisons = (
        [ExperimentComparison.model_validate(c) for c in _read_json(args.comparisons)]
        if args.comparisons
        else []
    )
    verdicts = validate_claims(claims, evidence, comparisons)
    failed = 0
    for claim_id, (verdict, reasons) in verdicts.items():
        print(f"{claim_id}: {verdict}")
        for reason in reasons:
            print(f"  - {reason}")
        failed += verdict != "CLAIM_SUPPORTED"
    return 0 if failed == 0 else 1


def cmd_report(args: argparse.Namespace) -> int:
    from verified_data_factory.business import (
        BusinessClaim,
        BusinessEvidence,
        CustomerValidation,
        ExperimentComparison,
        ExperimentResult,
        UnitEconomics,
        build_business_report,
        report_to_csv,
        report_to_json,
    )

    def _load(path: str | None, model: Any) -> list[Any]:
        return [model.model_validate(r) for r in _read_json(path)] if path else []

    economics = UnitEconomics.model_validate(_read_json(args.economics)) if args.economics else None
    report = build_business_report(
        report_id=args.report_id,
        release_manifests=_read_json(args.releases) if args.releases else [],
        comparisons=_load(args.comparisons, ExperimentComparison),
        results=_load(args.results, ExperimentResult),
        validations=_load(args.validations, CustomerValidation),
        evidence=_load(args.evidence, BusinessEvidence),
        claims=_load(args.claims, BusinessClaim),
        economics=economics,
        funnel_counts=_read_json(args.funnel) if args.funnel else {},
        hypothesis_verdict=args.hypothesis_verdict,
        hypothesis_detail=args.hypothesis_detail or "",
    )
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    Path(args.out_dir, "business_report.json").write_text(report_to_json(report), encoding="utf-8")
    Path(args.out_dir, "business_report.csv").write_text(report_to_csv(report), encoding="utf-8")
    print(f"verdict={report.hypothesis_verdict} report -> {args.out_dir}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from verified_data_factory.business import CustomerValidation, export_business_evidence

    validations = (
        [CustomerValidation.model_validate(r) for r in _read_json(args.validations)]
        if args.validations
        else []
    )
    written = export_business_evidence(
        out_dir=args.out_dir,
        report_json=Path(args.report_json).read_text(encoding="utf-8"),
        report_markdown=Path(args.report_markdown).read_text(encoding="utf-8"),
        experiments=_read_json(args.experiments) if args.experiments else [],
        benchmarks=_read_json(args.benchmarks) if args.benchmarks else [],
        economics=_read_json(args.economics) if args.economics else None,
        validations=validations,
        claims=_read_json(args.claims) if args.claims else [],
        include_feedback_text=args.include_feedback_text,
    )
    print(f"exported {len(written)} files -> {args.out_dir}")
    return 0


def register_business_commands(subparsers: argparse._SubParsersAction[Any]) -> None:
    """Attach `factory business ...` to the root parser (called by cli.py)."""
    business = subparsers.add_parser("business", help="Commercial & GTM Validation commands")
    bsub = business.add_subparsers(dest="business_command", required=True)

    p_bench = bsub.add_parser("benchmark", help="Private benchmark lifecycle")
    bench_sub = p_bench.add_subparsers(dest="benchmark_command", required=True)
    b_create = bench_sub.add_parser("create", help="Create (and optionally freeze) a benchmark")
    b_create.add_argument("--items", required=True, help="benchmark items JSONL")
    b_create.add_argument("--benchmark-version", default="1.0")
    b_create.add_argument("--split", default="private_benchmark")
    b_create.add_argument("--evaluation-policy", default="owner-harness-execution")
    b_create.add_argument("--scoring-policy", default="aggregation-v1")
    b_create.add_argument(
        "--privacy-level", default="PRIVATE", choices=["PUBLIC", "INTERNAL", "PRIVATE"]
    )
    b_create.add_argument("--dataset-release-id", default=None)
    b_create.add_argument("--freeze", action="store_true")
    b_create.add_argument("--output", required=True)
    b_create.set_defaults(func=cmd_benchmark_create)
    b_validate = bench_sub.add_parser("validate", help="Validate benchmark membership")
    b_validate.add_argument("--benchmark", required=True)
    b_validate.add_argument("--items", required=True)
    b_validate.set_defaults(func=cmd_benchmark_validate)
    b_contam = bench_sub.add_parser("contamination", help="Check training overlap")
    b_contam.add_argument("--benchmark-id", required=True)
    b_contam.add_argument("--items", required=True)
    b_contam.add_argument("--training-ids", default=None, help="JSONL with record_id per line")
    b_contam.add_argument("--training-groups", default=None, help="JSON list of group dicts")
    b_contam.add_argument("--output", default=None)
    b_contam.set_defaults(func=cmd_benchmark_contamination)

    p_exp = bsub.add_parser("experiment", help="Model-value experiments")
    exp_sub = p_exp.add_subparsers(dest="experiment_command", required=True)
    e_create = exp_sub.add_parser("create", help="Create an experiment contract from YAML")
    e_create.add_argument("--config", required=True)
    e_create.add_argument("--output", required=True)
    e_create.set_defaults(func=cmd_experiment_create)
    e_run = exp_sub.add_parser("run", help="Bind a config to outcome artifacts")
    e_run.add_argument("--config", required=True, help="experiment contract JSON")
    e_run.add_argument(
        "--outcomes", required=True, help="dir with baseline/control/treatment.jsonl"
    )
    e_run.add_argument("--run-id", required=True)
    e_run.add_argument("--output", required=True)
    e_run.add_argument("--failure-mode", action="append", default=[])
    e_run.add_argument("--threshold-pp", type=float, default=None)
    e_run.add_argument("--primary-metric", default="execution_accuracy")
    e_run.add_argument("--min-n", type=int, default=0)
    e_run.set_defaults(func=cmd_experiment_run)

    p_compare = bsub.add_parser("compare", help="Compare baseline vs treatment from a result")
    p_compare.add_argument("--result", required=True)
    p_compare.add_argument("--output", default=None)
    p_compare.add_argument("--threshold-pp", type=float, default=None)
    p_compare.add_argument("--primary-metric", default="execution_accuracy")
    p_compare.add_argument("--min-n", type=int, default=0)
    p_compare.set_defaults(func=cmd_experiment_compare)

    p_econ = bsub.add_parser("economics", help="Unit economics from a cost model")
    p_econ.add_argument("--costs", default=None, help="cost model JSON")
    p_econ.add_argument("--golden-records", type=int, required=True)
    p_econ.add_argument("--output", default=None)
    p_econ.set_defaults(func=cmd_economics)

    p_cust = bsub.add_parser("customer", help="Customer validation records")
    cust_sub = p_cust.add_subparsers(dest="customer_command", required=True)
    c_record = cust_sub.add_parser("record", help="Record one interaction")
    c_record.add_argument("--input", required=True)
    c_record.add_argument("--output", required=True)
    c_record.set_defaults(func=cmd_customer_record)

    p_pilot = bsub.add_parser("pilot", help="Pilot tracking")
    pilot_sub = p_pilot.add_subparsers(dest="pilot_command", required=True)
    pl_create = pilot_sub.add_parser("create", help="Create a pilot")
    pl_create.add_argument("--input", required=True)
    pl_create.add_argument("--output", required=True)
    pl_create.set_defaults(func=cmd_pilot_create)
    pl_trans = pilot_sub.add_parser("transition", help="Transition pilot status")
    pl_trans.add_argument("--pilot", required=True)
    pl_trans.add_argument(
        "--status", required=True, choices=["PLANNED", "ACTIVE", "COMPLETED", "PAUSED", "CANCELLED"]
    )
    pl_trans.add_argument("--end-date", default=None)
    pl_trans.add_argument("--output", required=True)
    pl_trans.set_defaults(func=cmd_pilot_transition)
    pl_eval = pilot_sub.add_parser("evaluate", help="Evaluate success criteria")
    pl_eval.add_argument("--pilot", required=True)
    pl_eval.add_argument("--observed", default=None, help="observed metrics JSON")
    pl_eval.add_argument("--output", required=True)
    pl_eval.set_defaults(func=cmd_pilot_evaluate)

    p_claims = bsub.add_parser("claims", help="Claim/evidence validation")
    claims_sub = p_claims.add_subparsers(dest="claims_command", required=True)
    cl_validate = claims_sub.add_parser("validate", help="Validate claims against evidence")
    cl_validate.add_argument("--claims", required=True)
    cl_validate.add_argument("--evidence", required=True)
    cl_validate.add_argument("--comparisons", default=None)
    cl_validate.set_defaults(func=cmd_claims_validate)

    p_report = bsub.add_parser("report", help="Build the business validation report")
    p_report.add_argument("--report-id", required=True)
    p_report.add_argument("--out-dir", required=True)
    p_report.add_argument("--releases", default=None)
    p_report.add_argument("--comparisons", default=None)
    p_report.add_argument("--results", default=None)
    p_report.add_argument("--validations", default=None)
    p_report.add_argument("--evidence", default=None)
    p_report.add_argument("--claims", default=None)
    p_report.add_argument("--economics", default=None)
    p_report.add_argument("--funnel", default=None)
    p_report.add_argument(
        "--hypothesis-verdict",
        default="INSUFFICIENT_EVIDENCE",
        choices=["HYPOTHESIS_SUPPORTED", "HYPOTHESIS_NOT_SUPPORTED", "INSUFFICIENT_EVIDENCE"],
    )
    p_report.add_argument("--hypothesis-detail", default="")
    p_report.set_defaults(func=cmd_report)

    p_export = bsub.add_parser("export", help="Export the business-validation/ tree")
    p_export.add_argument("--out-dir", required=True)
    p_export.add_argument("--report-json", required=True)
    p_export.add_argument("--report-markdown", required=True)
    p_export.add_argument("--experiments", default=None)
    p_export.add_argument("--benchmarks", default=None)
    p_export.add_argument("--economics", default=None)
    p_export.add_argument("--validations", default=None)
    p_export.add_argument("--claims", default=None)
    p_export.add_argument("--include-feedback-text", action="store_true")
    p_export.set_defaults(func=cmd_export)
