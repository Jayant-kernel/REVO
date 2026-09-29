# Model-value experiments

## The contract

An experiment binds a content-addressed `ExperimentConfig` to
owner-supplied outcome artifacts:

```text
experiment_id = SHA256(canonical_json({
  benchmark, baseline, treatment, (control),
  model, model_revision, training_config,
  evaluation_config, experiment_version }))
```

Timestamps, run ids, durations, and output paths never enter the
identity — rebuilding the same config yields the same id (tested).

## Arms

- **Baseline**: base model, no additional data (`adaptation_method: NONE`).
- **Control** (optional, recommended): base model + generic synthetic
  data. Tests whether *verification* adds value, not just *more data*.
- **Treatment**: base model + Verified Data Factory release
  (`training_dataset_release_id`).

Adaptation methods (`SFT`, `LoRA`, `FULL_FINE_TUNE`,
`RETRIEVAL_CONTEXT`, `PROMPT_ONLY`, `OTHER`, `NONE`) are metadata. The
system does not train models: the `artifact` adapter reads outcome
files, the `external` adapter invokes a controlled command that must
emit them. No cloud GPU orchestration, no Kubernetes, no scheduler.

## Evaluation

Correctness comes from the owner's harness (ideally Phase 3/4
infrastructure or equivalent) and arrives as per-item outcomes
`{record_id, correct, family, edge_cases, latency_ms?, error_type?}`.
Phase 8 aggregates only — it implements no second correctness system
and requires no proprietary inference API.

Evaluation MUST use a dataset not used for training: the private
benchmark (§10–§11), frozen and contamination-checked before use.

## Canonical template: VERIFIED DATA VALUE

`business.experiments.verified_value_template` builds the
baseline/control/treatment contract from a benchmark id, a verified
release id, a generic-data reference, and a model. Primary metric:
execution correctness. Secondary: family accuracy, edge-case accuracy,
invalid-SQL rate, latency. The template runs only when real
datasets/models exist — it never fabricates a result.

## Verdicts

`judge_hypothesis` applies configurable criteria
(`primary_metric`, `improvement_threshold_pp`,
`minimum_benchmark_size`, `minimum_repeated_runs`,
`minimum_family_coverage`) and returns exactly one of
`HYPOTHESIS_SUPPORTED`, `HYPOTHESIS_NOT_SUPPORTED`,
`INSUFFICIENT_EVIDENCE`. No universal thresholds are hardcoded.
