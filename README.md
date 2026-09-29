# Verified SQL Data Factory

A **verification-first synthetic data factory** for AI coding/data agents.

Long-term goal: commercially usable, execution-verified SQL training and
evaluation data — where every record ships with executable proof of
correctness, not just model-generated text.

## Current phase

**Phase 8 — Commercial, GTM & Customer Validation** (implemented).

> Task Engine + Candidate Generation + Secure Execution + Independent
> Verification + Quality & Audit + Provenance + Data Products +
> Business Validation are implemented. The system measures model value
> (private benchmarks, baseline/control/treatment experiments, paired
> statistics), records customer validation with code-enforced honesty
> rules, tracks unit economics with explicit unknowns, and assembles
> auditable business reports — never inventing customers, revenue, or
> model improvements. Core hypothesis status: **INSUFFICIENT_EVIDENCE**
> (no real-model experiment has run yet).

## Current scope

- Domain: **analytical SQL**
- Engine: **DuckDB**
- Customers (initial): AI startups / teams building SQL agents, data agents,
  analytics agents, coding/data assistants, post-training and eval systems.

## Long-term architecture (8 layers)

```text
Task Engine
     ↓
Generation
     ↓
Sandbox
     ↓
Verification
     ↓
Quality
     ↓
Provenance
     ↓
Data Products
     ↓
Commercialization
```

See `docs/architecture.md` for the full layer definitions,
`docs/roadmap.md` for Phases 0–8, and `docs/phase-1-task-engine.md` for the
Task Engine implementation.

## Task Engine (Phase 1)

Declarative YAML templates (`templates/sql/`) → validated `TaskTemplate` →
`generate_task(template, seed)` → reproducible `TaskInstance` with seeded
DuckDB fixtures. 10 families, 100-task catalog in `configs/task_catalog.yaml`.

```powershell
pip install -e ".[test]"
factory task list
factory task generate --template sql.retention.30_day --seed 12345
factory task export --catalog configs/task_catalog.yaml --output tasks.jsonl
factory generate one --template sql.joins.simple --seed 101 --provider fake
factory generate batch --catalog configs/task_catalog.yaml --provider fake
factory production plan --config configs/production/smoke_qualification_001.yaml
factory production preflight --config configs/production/smoke_qualification_001.yaml
pytest
```

Deterministic seeds: same template version + config + seed (+ engine
version `1.0.0`) → identical canonical task. Task ids are input-hashed:
`sql.retention.30_day.v1.<12-hex>` (seed and inputs stay as separate fields).

Frozen contracts: `docs/phase-1-contract.md` (inputs, outputs, guarantees,
Phase 2 API) and `docs/task-semantics.md` (per-family oracle reference).

## Docs map

- `docs/architecture.md` — 8-layer target architecture
- `docs/roadmap.md` — Phase 0 → Phase 8 plan
- `docs/technical-stack.md` — intended stack (Python 3.12+, Pydantic, DuckDB, pytest, …)
- `docs/data-model.md` — conceptual entities + relationships
- `docs/golden-record.md` — what one verified record contains
- `docs/verification-principles.md` — 10 verification principles
- `docs/security.md` — sandbox threat model (generated code = hostile)
- `docs/licensing.md` — license/provenance policy
- `docs/metrics.md` — generation / verification / dataset / economics metrics
- `docs/first-experiment.md` — 100 tasks × 3 candidates design
- `docs/business-validation.md` — sample → pilot → sale sequence
- `docs/definition-of-done.md` — Phase 0 exit criteria
- `docs/phase-1-task-engine.md` — Task Engine implementation
- `docs/phase-1-contract.md` — frozen Phase 1 input/output guarantees
- `docs/task-semantics.md` — per-family semantic reference for verification
- `docs/phase-2-generation.md` — Candidate Generation implementation
- `docs/phase-3-sandbox.md` — Secure Execution Sandbox (as-built)
- `docs/phase-4-verification.md` — Independent Verification Engine (as-built)
- `docs/phase-3-4-integration.md` — integration gate: real-Docker evidence
- `docs/phase-5-quality.md` — Dataset Quality & Audit (as-built)
- `docs/quality-metrics.md` — metric definitions for health reports
- `docs/golden-selection.md` — Golden qualification rules
- `docs/audit.md` — risk-based human audit sampling
- `docs/phase-6-provenance.md` — Provenance & Reproducibility (as-built)
- `docs/production/START_PRODUCTION.md` — guarded smoke and production CLI workflow
- `docs/production/artifact-retention.md` — immutable run evidence and Git policy
- `docs/provenance-model.md` — node/edge model, identity, canonicalization
- `docs/reproducibility.md` — layered reproducibility levels and statuses
- `docs/provenance-bundle.md` — bundle format, diffing, CLI usage
- `docs/adr/` — ADR-001…ADR-009

## Development workflow

Requires Python 3.12+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[test]"
pytest
```

Conventions:

- Typed Python (`mypy --strict` target), simple architecture, no premature abstractions.
- YAML configs validated with Pydantic; never commit secrets, weights, or datasets.
- Deterministic behavior wherever possible; architectural changes via ADRs.
- Never claim something is implemented when it is only planned.

## Status / non-goals

Intentionally **not** implemented through Phase 7: model training,
fine-tuning, marketplace integration, payments, licensing automation,
cloud orchestration, production APIs, auth, UI, cloud/K8s, deployments.
No LLM judge exists. No cloud artifact storage, blockchain, or Sigstore.

Build the sandbox image (needs a Docker daemon + build-time network):

```powershell
docker build -f src/verified_data_factory/sandbox/docker/Dockerfile `
  -t verified-data-factory-sandbox:1.0 `
  src/verified_data_factory/sandbox
```

Run Phase 5 on verified records:

```powershell
factory quality dataset --input records.jsonl --config configs/quality_example.yaml --out-dir out/
```

Record Phase 6 provenance for a Golden set:

```powershell
factory provenance record --records records.jsonl --qualities qualities.jsonl --golden out/golden.jsonl --name my-set --out provenance-bundle/
factory provenance validate --bundle provenance-bundle/
```

Phase 7 handoff: `provenance_bundle/` (manifest, reproduction, snapshot,
nodes/edges/activities, artifacts, golden records, reproducibility,
completeness) carries everything data-product work needs to reference —
not rebuild — Golden dataset snapshots.

Build a Phase 7 product release from a Golden snapshot:

```powershell
factory product build --golden out/golden.jsonl --quality qualities.json --snapshot provenance-bundle/snapshot.json --config configs/product_example.yaml --out-dir release/
factory product validate --release-dir release/
```
