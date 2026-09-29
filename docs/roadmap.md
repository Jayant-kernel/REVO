# Roadmap — Verified SQL Data Factory

Status: **Phase 0 is current. Phases 1–8 are planned, not started.**

## Phase 0 — Foundation (current)

Deliver:

- Architecture (`docs/architecture.md`)
- Requirements/scope (this repo's Phase 0 brief + README)
- Repository structure (`src/`, `tests/`, `configs/`, `templates/`, `docs/`)
- Technology decisions (`docs/technical-stack.md`, `docs/adr/`)
- Data model design (`docs/data-model.md`, `docs/golden-record.md`)
- Security principles (`docs/security.md`)
- Verification principles (`docs/verification-principles.md`)
- Licensing/provenance principles (`docs/licensing.md`)
- Metrics (`docs/metrics.md`)
- First experiment + business validation (`docs/first-experiment.md`, `docs/business-validation.md`)
- Development conventions (README + `docs/definition-of-done.md`)
- Definition of Done

Exit criteria: see `docs/definition-of-done.md`.

## Phase 1 — Task Engine

Build:

- Task DSL + task templates + task registry
- Deterministic fixture generator (seeded)
- Task models + schema validation (Pydantic)
- Instruction generation
- Initial SQL task families:
  1. Simple JOINs
  2. Multi-table JOINs
  3. GROUP BY / aggregation
  4. CTEs
  5. Subqueries
  6. Window functions
  7. Date/time analysis
  8. Deduplication
  9. Customer retention
  10. Funnel/session analysis

Target: **100 reproducible tasks** before scaling further.

## Phase 2 — Candidate Generation

Build:

- Model adapter abstraction (+ router)
- Qwen integration, Devstral integration
- Prompt management (versioned)
- Candidate parsing + normalization
- Candidate storage
- Multiple-candidate generation

Prerequisite: explicit license/provenance records for each model
(see `docs/licensing.md`).

## Phase 3 — Secure Execution (implemented)

Built:

- Disposable Docker execution (`--network none`, read-only root, dropped
  capabilities, non-root, PID/memory/CPU limits, timeout + kill + remove)
- DuckDB lockdown (external access/filesystems/extensions off)
- Single-statement SQL policy gate, output/row/byte caps
- `ExecutionResult` collection (execution-only, no verdicts)

See `docs/phase-3-sandbox.md` (as-built) and `docs/security.md`.

## Phase 4 — Verification (implemented)

Built:

- Independent Python oracles for all 10 families (no SQL oracles, no LLM judge)
- Hidden fixtures, property + metamorphic checks, mutation scoring
- PASS/FAIL/INCONCLUSIVE verdicts with evidence; weak suites never blame candidates

See `docs/phase-4-verification.md` (as-built) and `docs/verification-principles.md`.

## Phase 5 — Quality & Audit (implemented)

Built:

- Task-quality, verification-evidence, duplicate (exact/structural/semantic),
  diversity, coverage, difficulty, contamination analysis
- Deterministic risk-based audit sampling + JSONL results
- Golden selection with explainable gates + dataset health reports

See `docs/phase-5-quality.md` (as-built).

## Phase 6 — Provenance (implemented)

Built:

- Content-addressed lineage graph (nodes/edges/activities, JSONL store)
- Canonical serialization + SHA-256 identities + streaming artifact hashes
- Source/environment/model/configuration snapshots (secrets never captured)
- Dataset snapshots, run + reproduction manifests, completeness validation
- Layered reproducibility assessment + manifest comparison (no auto-replay)

See `docs/phase-6-provenance.md` (as-built).

## Phase 7 — Dataset Products (implemented)

Built:

- Versioned product model (snapshot + config + schema + split + format → release)
- TRAIN / PUBLIC_EVAL / PRIVATE_EVAL / BENCHMARK / SAMPLE profiles with code-enforced visibility
- Deterministic group-aware splitting + sharded JSONL/Parquet export
- Content-defined release ids, SHA256SUMS, dataset cards, previews, metrics passthrough
- Build-time self-validation, strict loading, release diffing
- `factory product build|validate|diff|load|splits` CLI

See `docs/phase-7-products.md` (as-built).

## Phase 8 — Commercialization (implemented)

Built:

- Classified evidence model (OBSERVED/MEASURED/USER_REPORTED/ASSUMED/UNKNOWN/TEST_FIXTURE)
- Private benchmark lifecycle (create/freeze/validate/contamination-check) + release references
- VERIFIED DATA VALUE experiment contracts (baseline/control/treatment), artifact + external adapters
- Aggregation scoring, paired statistics (exact McNemar, Wilson), repeated-run variance, configurable verdicts
- Unit economics with explicit unknowns, SCENARIO tables, ASSUMED-until-validated pricing
- Customer validation records (no PII fields), willingness ladder, pilot lifecycle, funnel counts
- Claim/evidence validator with numeric matching, maturity derivation, redacted exports
- `business_report.json/csv`, `business-validation/` export, `docs/gtm/` materials, pilot packages
- `factory business benchmark|experiment|compare|economics|customer|pilot|claims|report|export` CLI

Core hypothesis status: **INSUFFICIENT_EVIDENCE** — framework proven on
fixtures; no real-model experiment, customer, or price observed yet.

See `docs/phase-8-business.md` (as-built).

## Explicit non-goals per phase

- Phase 0 builds no pipeline code (enforced by structural test).
- No phase claims success on generation volume alone; the gating metric is
  **cost per genuinely useful verified example** (see `docs/metrics.md`).
