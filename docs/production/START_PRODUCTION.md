# Starting a guarded production run

The supported interface is the `factory production` CLI. There is no production API and none is required for the current local workflow.

Install the editable project once so the `factory` command is available:

```powershell
python -m pip install -e ".[dev]"
```

If the editable command is not installed, use the equivalent source-tree form:

```powershell
$env:PYTHONPATH = "src"
python -m verified_data_factory.cli production --help
```

## Recommended sequence

Start with the disposable 10-task, 30-candidate smoke configuration. It covers all ten SQL families and is explicitly labeled `REVIEW_REQUIRED_NON_COMMERCIAL` because checkpoint rights are unresolved.

```powershell
factory production plan --config configs/production/smoke_qualification_001.yaml
factory production preflight --config configs/production/smoke_qualification_001.yaml
factory production run --config configs/production/smoke_qualification_001.yaml --run runs/smoke-qualification-001 --execute
factory production status --run runs/smoke-qualification-001
factory production report --run runs/smoke-qualification-001 --output runs/smoke-qualification-001/reports/production-report.json
```

`plan` is read-only. `preflight` must pass the exact model digest, pinned sandbox digest, Docker, configuration, storage, secrets, and stale-container checks. `run` refuses a different destination and refuses to create a manifest when preflight fails.

Every execution authorization permits at most one batch. A successful non-terminal batch ends in `AWAITING_BATCH_AUTHORIZATION`; inspect status, family/failure reports, novelty, diversity, elapsed time, and audit samples before invoking `run --execute` again. A `PAUSED`, `TARGET_REACHED`, or other terminal state cannot continue automatically.

Only after the smoke run is reviewed and checkpoint governance is explicitly accepted should Batch 1 of Production-002 be authorized:

```powershell
factory production plan --config configs/production/production_sql_v2.yaml
factory production preflight --config configs/production/production_sql_v2.yaml
factory production run --config configs/production/production_sql_v2.yaml --run runs/production-002 --execute
```

Production-002 Batch 1 is 500 tasks × 3 candidates. Do not start it merely because preflight is green. Changing model identity, revision, prompt, sampling, task seeds, sandbox, verification, or quality policy creates a new configuration identity and requires a new run identity.

Commercial/public release remains blocked until model governance is `COMMERCIALLY_CLEARED`, human audit is complete, a dataset snapshot is frozen, and release validation passes.
