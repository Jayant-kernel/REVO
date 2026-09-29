# Technical Stack — Verified SQL Data Factory

Status: **Phase 0 — intended stack. Only `pyproject.toml` core deps are installed now.**

## Planned stack

### Programming

- **Python 3.12+** (typed Python required; `mypy --strict` target).

### Task / data schemas

- **Pydantic v2** — task models, fixture schemas, record validation.

### SQL execution

- **DuckDB** — initial execution engine (see ADR-002).
  Added as an dependency in Phase 1 (`project.optional-dependencies.sql`),
  not required for Phase 0.

### Testing

- **pytest** — unit/integration tests from Phase 1 onward.
- **Hypothesis** — property-based testing (Phase 4 verification work).

### Configuration

- **YAML + Pydantic validation** — human-editable configs in `configs/`,
  validated at load time. Never commit secrets (see `.gitignore`).

### Packaging

- **`pyproject.toml`** (Hatchling backend). Source layout under `src/`.

### Initial storage

- **Local filesystem** for Phase 1–2 artifacts + fixtures.

### Future metadata database

- **PostgreSQL** — when record volume / querying outgrows local files
  (Phase 6 provenance work). Not provisioned in Phase 0.

### Future sandbox

- **Docker with strict isolation** — starting point only.
  Docker alone is not a complete security boundary (see `docs/security.md`).

### Future model serving

- **vLLM and/or another open-weight model-serving system** — Phase 2 decision.
  No model server is set up in Phase 0.

## What is installed in Phase 0

`pyproject.toml` declares only:

- `pydantic>=2.0`, `pyyaml>=6.0` (runtime, minimal)
- `pytest` (dev/test), with `duckdb` / `hypothesis` / `ruff` / `mypy`
  available via `project.optional-dependencies` when the phase that needs
  them arrives.

## Dependency policy

- Do not install a future technology just because it appears here.
- Each new dependency needs a reason: the phase that uses it + what it replaces.
- Prefer standard library over new dependencies; prefer isolated modules
  over framework-heavy abstractions.
