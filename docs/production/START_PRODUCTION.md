# Starting a production run

Production is not started by this preparation work. The configuration is frozen at `configs/production/production_sql_v1.yaml` and has a content-defined configuration ID.

1. Run `factory production preflight --config configs/production/production_sql_v1.yaml` and resolve every failed required check.
2. Run `factory production plan --config configs/production/production_sql_v1.yaml`. This is a dry run: it makes zero model calls, Docker executions, candidates, or Golden decisions.
3. Review the pinned model digest, `sql-v2` prompt version, sampling settings, budget caps, and output path.
4. In a separately authorized execution task, enable and run the reviewed production runner using the frozen configuration.
5. Use `factory production status --run runs/production-sql-v1` to monitor checkpoints.
6. Use `factory production report --run runs/production-sql-v1 --output runs/production-sql-v1/reports/production-report.json` for aggregate evidence.
7. Inspect family and failure reports after every batch. Pause on configured systematic-problem triggers; do not silently change the model or prompt.
8. Complete the deterministic risk-based audit.
9. Create a Phase 6 dataset snapshot only after Golden membership, quality, contamination, and audit requirements are final.
10. Build and validate the Phase 7 release, then freeze it. A private benchmark may only use eligible held-out records.

Changing model identity/revision, prompt version, sampling, candidate count, task seed policy, sandbox policy, verification policy, or quality policy requires a new configuration identity and a new operational run.
