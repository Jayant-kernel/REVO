# Production artifact retention

Production and qualification outputs under `runs/` are local evidence, not source code. They are intentionally excluded from Git because the current tree contains generated datasets, raw model output, database files, and potentially large release artifacts.

- Never rewrite or reuse a historical run directory.
- Give every new run a unique, configuration-bound identity.
- Preserve the manifest, state, candidates, executions, verification, quality, provenance, reports, and audit decisions together.
- Store any shared or released evidence in an approved artifact store with immutable hashes; Git is not that store.
- Do not treat an ignored artifact as disposable merely because it is absent from source control.
- Do not publish artifacts while the checkpoint is labeled `REVIEW_REQUIRED_NON_COMMERCIAL`.

The repository tracks the code, frozen configuration, and documentation needed to reproduce a run. The run manifest records the configuration ID, exact model ID/revision, provider, endpoint, prompt version, and governance status.
