# Definition of Done — Phase 0

Phase 0 is complete when all of the following hold:
- [ ] Project scope is documented (README + roadmap)
- [ ] 8-layer architecture is documented (`docs/architecture.md`)
- [ ] Initial technical stack is documented (`docs/technical-stack.md`)
- [ ] Data model is documented (`docs/data-model.md`)
- [ ] Golden Record concept is documented (`docs/golden-record.md`)
- [ ] Verification principles are documented (`docs/verification-principles.md`)
- [ ] Security principles are documented (`docs/security.md`)
- [ ] Licensing principles are documented (`docs/licensing.md`)
- [ ] Metrics are documented (`docs/metrics.md`)
- [ ] First technical experiment is documented (`docs/first-experiment.md`)
- [ ] Business validation plan is documented (`docs/business-validation.md`)
- [ ] Repository structure exists (`src/`, `tests/`, `configs/`, `templates/`, `docs/`)
- [ ] ADR system exists with ADR-001…ADR-007 (`docs/adr/`)
- [ ] README explains the project + current phase + status
- [ ] `.gitignore` covers models, datasets, secrets, binaries, venvs
- [ ] No premature production implementation exists (no task engine, LLM
      integration, sandbox, verification, quality, dataset, API, or infra code)
- [ ] Structural checks pass (`pytest tests/test_phase0_structure.py`)

---

# Definition of Done — Phase 5

Phase 5 is complete when all of the following hold:

- [ ] `quality/` package exists and consumes Phase 4 outputs directly
- [ ] Task-quality, verification-evidence, duplicate (exact/structural/semantic),
      diversity, coverage, difficulty, contamination analysis all work
- [ ] Deterministic risk-based audit sampling + JSONL results work
- [ ] Golden selection with explainable gates works; PASS alone never suffices
- [ ] Golden/Excluded/Inconclusive/Audit export works; health report works
- [ ] Failures remain explainable; decisions carry reasons
- [ ] Repeated runs produce identical decisions and export bytes
- [ ] `factory quality ...` CLI works on Phase 1–4 artifacts
- [ ] `docs/phase-5-quality.md`, `docs/quality-metrics.md`,
      `docs/golden-selection.md`, `docs/audit.md`, ADR-008 exist
- [ ] Tests cover positive and negative cases (see `tests/quality_dataset.py`)
- [ ] Ruff, formatting, and strict mypy are clean
- [ ] The complete Phase 1–4 suite remains green

---

# Definition of Done � Phase 6

Phase 6 is complete when all of the following hold:

- [ ] `provenance/` package exists; Phases 1�5 behavior is unchanged
- [ ] Content-derived IDs, canonical serialization, and artifact hashing work
- [ ] Nodes/edges/activities, task/candidate/execution/verification/quality/
      audit/Golden lineage, and source/environment/model/config snapshots work
- [ ] Dataset snapshots, completeness validation, and layered reproducibility
      assessment (with honest non-VERIFIED statuses) work
- [ ] Provenance bundle export works; CLI works; public API works
- [ ] Deterministic comparison works; security/secret tests pass
- [ ] End-to-end TaskInstance ? Golden Snapshot provenance test passes
- [ ] Full existing test suite remains green
- [ ] Ruff, formatting, and strict mypy are clean
- [ ] `docs/phase-6-provenance.md`, `docs/provenance-model.md`,
      `docs/reproducibility.md`, `docs/provenance-bundle.md`, ADR-009 exist

---

# Definition of Done — Phase 7

Phase 7 is complete when all of the following hold:

- [ ] `products/` package exists; Phases 1–6 behavior is unchanged
- [ ] Product model (snapshot + config + schema + split + format → release),
      five profiles, and code-enforced PUBLIC visibility work
- [ ] Deterministic group-aware splitting (twice-build identical release ids)
      and sharded JSONL/Parquet export work
- [ ] Release manifests, SHA256SUMS, dataset cards, previews, and referenced
      (not recomputed) metrics work
- [ ] Build-time self-validation, strict loading, and release diffing work;
      `factory product ...` CLI works on Phase 5–6 artifacts
- [ ] Full existing test suite remains green
- [ ] Ruff, formatting, and strict mypy are clean
- [ ] `docs/phase-7-products.md`, `docs/product-model.md`, `docs/splits.md`,
      `docs/release-format.md`, `docs/consuming-products.md`, ADR-010 exist

---

# Definition of Done — Phase 8

Phase 8 is complete when all of the following hold:

- [ ] `business/` package exists; Phases 1–7 behavior is unchanged
- [ ] Classified evidence model + structured claims exist; TEST_FIXTURE quarantined
- [ ] Private benchmark lifecycle (create/freeze/validate) + 5-category
      contamination checks + release references with visibility enforcement exist
- [ ] VERIFIED DATA VALUE template, baseline/control/treatment runs, artifact +
      external adapters exist; no training platform, no proprietary API requirement
- [ ] Aggregation scoring (primary/secondary), pp-vs-relative math, family/edge
      tables, exact McNemar + Wilson statistics, repeated-run variance exist
- [ ] Configurable hypothesis verdicts incl. INSUFFICIENT_EVIDENCE exist
- [ ] Cost model with explicit unknowns, unit economics, SCENARIO tables,
      ASSUMED-until-validated pricing exist
- [ ] Customer validation (no PII fields), willingness ladder with evidence
      gates, pilot lifecycle + criteria, funnel counts exist
- [ ] Claim validator (numeric matching) + maturity derivation + redacted
      exports + secret scrubbing exist
- [ ] `business_report.json/csv`, `business-validation/` export,
      `docs/roadmap-evidence.json`, `docs/gtm/` (8 files), technical datasheet,
      pilot packages exist
- [ ] `factory business ...` CLI works; public API works
- [ ] Negative results preserved; no unsupported market claims generatable;
      no payments/CRM; no Phase 1–7 contract changes
- [ ] Full existing test suite remains green
- [ ] Ruff, formatting, and strict mypy are clean
- [ ] `docs/phase-8-business.md`, `docs/experiments.md`, `docs/model-value.md`,
      `docs/customer-validation.md`, `docs/economics.md`, `docs/gtm/`, ADR-011 exist
