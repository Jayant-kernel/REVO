# Architecture — Verified SQL Data Factory

Status: **Phase 0 — planning / design only. Nothing described here is implemented yet.**

## 1. Purpose

The Verified SQL Data Factory will eventually generate **commercially usable,
execution-verified synthetic SQL training and evaluation data** for AI
coding/data agents.

The differentiator is not generation alone, but the full verification chain:

```text
synthetic generation
+
independent execution
+
independent oracle
+
hidden tests
+
property testing
+
metamorphic testing
+
mutation testing
+
performance testing
+
provenance
+
reproducibility
```

## 2. End-to-end flow (target state)

```text
Task specification
        ↓
Open-weight model generates candidate solution
        ↓
Execute candidate in isolated sandbox
        ↓
Independent oracle + hidden tests + property tests
        ↓
Verify correctness
        ↓
Quality checks
        ↓
Verified dataset
        ↓
Training / evaluation / commercial distribution
```

## 3. The 8 layers

### Layer 1 — Task Engine

**Responsibility:** define and generate structured computational tasks.

Eventual scope:

- Task templates and a task DSL
- Schemas, fixtures, and edge cases
- Task difficulty grading
- Task registry (versioned, reproducible)

Design constraints (see ADR-005, ADR-006):

- Task specifications are authoritative over natural-language prompts.
- Every task instance must be deterministically recreatable from
  (template version, seed).

Phase: 1. **Not implemented in Phase 0.**

### Layer 2 — Generation

**Responsibility:** obtain candidate solutions from open-weight models.

Eventual scope:

- Model adapters + model router (common interface across models)
- Prompt management and versioning
- Candidate generation (including multi-candidate sampling)
- Output parsing and candidate normalization
- Candidate storage

Initial planned models (documented only, not integrated):

- `Qwen3-Coder-30B-A3B-Instruct`
- `Devstral-Small-2-24B-Instruct-2512`
- `Qwen3-30B-A3B-Thinking-2507` (optional reasoning / teacher model)

License records for each model are required before any use
(see `docs/licensing.md`).

Phase: 2. **Not implemented in Phase 0.**

### Layer 3 — Verification

**Responsibility:** determine whether a candidate actually satisfies the task.

Eventual scope:

- Independent oracle (reference solution computed independently of the candidate)
- Public tests, hidden tests
- Property-based tests, metamorphic tests
- Mutation testing (to measure test-suite strength)
- Performance checks
- Correctness classification

Critical principle (see ADR-004, `docs/verification-principles.md`):

> Correctness must not depend solely on an LLM judging another LLM.

Executable, deterministic validation is preferred wherever possible.

Phase: 4. **Not implemented in Phase 0.**

### Layer 4 — Sandbox

**Responsibility:** safely execute untrusted generated workloads.

Eventual scope:

- Isolated, ephemeral execution environments
- No network access
- Non-root execution
- Restricted filesystem, restricted syscalls
- Resource limits (CPU / memory / processes / time)
- Dependency allowlists
- Full cleanup after execution

Critical principle (see `docs/security.md`):

> Treat every generated program as potentially malicious.

> Docker alone is not considered a complete security boundary.

Phase: 3. **Not implemented in Phase 0.**

### Layer 5 — Quality

**Responsibility:** decide whether a *verified* example belongs in the
commercial dataset.

Passing tests is necessary but not sufficient. Eventual scope:

- Exact + semantic duplicate detection
- Task coverage and difficulty-distribution analysis
- Test-strength / mutation-score gating
- Solution diversity
- Ambiguity detection
- Human auditing workflow + dataset quality metrics

Phase: 5. **Not implemented in Phase 0.**

### Layer 6 — Provenance

**Responsibility:** track the complete history of every record.

Eventual scope (per-record metadata):

- Model + model revision
- Prompt version, task-template version, fixture seed
- Oracle version, test-suite version
- Container image digest, dependency versions
- Generation + verification timestamps
- Dataset version, licensing metadata

Goal: reproducibility and commercial/data provenance.

Phase: 6. **Not implemented in Phase 0.**

### Layer 7 — Data Products

Turns the verification infrastructure into shippable artifacts:

1. Training datasets
2. Preference datasets
3. Evaluation benchmarks
4. Failure datasets
5. RL environments
6. Verification APIs

Phase: 7. **Not implemented in Phase 0.**

### Layer 8 — Commercial / GTM

Eventual business surface:

- Direct dataset sales, evaluation pilots, custom datasets
- API access, enterprise licensing, data partnerships
- Marketplaces, recurring contracts

Potential future distribution channels (not integrated):

- Hugging Face, Datarade, AWS Data Exchange
- Databricks Marketplace, Snowflake Marketplace
- Direct sales / direct partnerships with AI data/model companies

Phase: 8. **Not implemented in Phase 0.**

## 4. Cross-cutting concerns

| Concern | Rule |
|---|---|
| Determinism | Seeds + versions must recreate any task, fixture, and verdict |
| Typing | Typed Python throughout |
| Testability | Modules independently testable; no hidden global state |
| Dependencies | No dependency without a reason; introduce at point of use |
| Honesty | Never claim a layer is implemented when it is only planned |
| Scope | No silent scope expansion; changes go through ADRs |

## 5. Repository mapping (target)

```text
src/verified_data_factory/
├── task_engine/     # Phase 1
├── generation/      # Phase 2
├── sandbox/         # Phase 3
├── verification/    # Phase 4
├── quality/         # Phase 5
├── provenance/      # Phase 6
└── datasets/        # Phase 7
```

Phase 0 deliberately leaves these packages absent
(verified by `tests/test_phase0_structure.py`).
