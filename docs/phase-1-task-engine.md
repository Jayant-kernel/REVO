# Phase 1 — Task Engine

Status: **implemented**. Generates structured, deterministic, reproducible SQL
tasks + DuckDB fixtures. No candidate generation, no verification (Phase 4),
no LLM, no network.

## 1. Architecture

```text
templates/sql/**/*.yaml          # declarative DSL (human-editable)
        ↓ template.py            # YAML → TaskTemplate (Pydantic-validated)
        ↓ registry.py            # TemplateRegistry: get / list / list_by_family
        ↓ generator.py           # generate_task(template, seed) → TaskInstance
        ├── seed.py              # child-seed derivation, task ids, ENGINE_VERSION
        ├── fixtures.py          # seeded row generation + DuckDB materialization
        ├── instruction.py       # TaskInstance → natural-language instruction
        ├── validation.py        # structural / schema / fixture / semantic checks
        ├── canonical.py         # canonical JSON + hash for equality
        ├── export.py            # JSON / JSONL round-trip
        └── schema.py            # DDL rendering, DuckDB type map
src/verified_data_factory/cli.py # thin `factory task ...` wrapper
configs/task_catalog.yaml        # 10 templates × 10 seeds = 100 tasks
```

Module boundaries mirror the Phase 0 brief: models, templates, registry,
generation, fixtures, instructions, validation, seeds stay separate and
import in one direction (generator orchestrates; nothing imports the CLI).

## 2. Task model

`TaskTemplate` (template_id, version, family, description, difficulty 1–5,
schema_definition, generation_config, requirements, edge_cases, oracle_spec,
instruction_template) and `TaskInstance` (task_id, template/version/seed,
family, difficulty, instruction, schema, tables, fixture_metadata,
requirements, constraints, edge_cases, oracle_spec, generation_metadata),
plus `ColumnDefinition`, `TableDefinition`, `OracleSpec`, `FixtureMetadata`.

The `schema` list is stored on the model as `schema_` (aliased to serialize
as `"schema"`) so no Pydantic `BaseModel.schema` shadowing occurs and no
warnings are emitted. External JSON/JSONL always uses `"schema"`.

`oracle_spec` is metadata only (`type: reference_query` + strategy) — the
oracle itself is Phase 4. The engine never executes candidate SQL.

## 3. DSL

YAML per template (`templates/sql/<area>/<name>.yaml`). Tables accept mapping
or list form; columns carry `name/type/nullable`; `row_count` + `row_kind`
drive generation; `requirements` hold task parameters; `edge_cases` use a
controlled vocabulary enforced in `validation.KNOWN_EDGE_CASES`; `oracle`
needs `type`/`strategy`. Malformed YAML, unknown types, missing fields, bad
edge cases, or bad oracle specs are rejected at load — never silently
registered.

## 4. Registry

`TemplateRegistry.register/get/list/list_by_family/metadata`, keyed by
`(template_id, version)` with duplicate detection. `load_builtin_registry()`
loads `templates/sql/`. New family = new YAML file, zero code changes.

## 5. Fixture generation

`generate_fixture_tables(template, seed)`: per-table `random.Random` streams
from `derive_child_seed(seed, "table:<name>")`; row counts jitter ±20% as
legitimate instance variation (seed differences never depend on it —
streams alone guarantee independence); realistic linked data
(customers → orders → order_items, customers → events); declared edge cases
intentionally injected *and enforced* (`apply_edge_cases` returns only what
is fixture-evidenced) and recorded. `materialize_duckdb()` builds an
in-memory (or temp-file) DuckDB database from DDL + inserts for tests and
local inspection. No `.duckdb` files are committed — tasks store
`fixture_metadata` (engine, seed, generation_version, row counts) sufficient
to recreate any fixture.

## 6. Seed-replay contract

```text
same template ID + same template version + same generation config
+ same seed + same ENGINE_VERSION (= 1.0.0)
= same canonical TaskInstance
```

Child seeds: `SHA256("{seed}:{stream}")[:8]`. Task ids:
`{template_id}.v{version}.{12-hex-hash}` over the canonical identity payload
(template id, version, generation config, seed, engine version) — stable,
order-independent, collision-resistant at scale; seeds 1M apart no longer
collide. Human-readable inputs stay as separate fields. `ENGINE_VERSION`
(`1.0.0`) names the behavior contract and must be bumped on any
behavior-breaking change (see `docs/phase-1-contract.md` for the
logical-vs-environment reproducibility boundary).

## 7. Instruction rendering

`render_instruction()` formats the template string over
(requirements + tables/table_list/edge_cases). The `TaskInstance` is the
source of truth (ADR-005); the instruction is a rendering. Unresolvable
placeholders raise `InstructionError`.

## 8. Validation

Structural (ids, versions, difficulty; `task_id` is recomputed from the
generation inputs and must match), schema (unique tables/columns,
supported DuckDB types, fixture↔schema column agreement, metadata row
counts), fixture (materializable, non-empty), semantics (FK-like consistency
orders→customers, items→orders/products, events→customers; requirement
column references; renderable instruction). Template load additionally
enforces per-family semantic keys (`SEMANTIC_REQUIREMENTS` — e.g. retention
needs `boundary_policy`; unknown families are rejected until registered).
All failures raise
domain exceptions (`TemplateError` / `ValidationError` / `FixtureError`).

## 9. CLI

```bash
factory task list [--family retention]
factory task show sql.retention.30_day
factory task generate --template sql.retention.30_day --seed 123
factory task generate --count 10 --seed 123
factory task validate task.json
factory task export --count 100 --seed 123                      # round-robin
factory task export --catalog configs/task_catalog.yaml --output tasks.jsonl
```

`export` ends with a seed-replay self-check (regenerate first task, compare
canonical JSON).

## 10. Adding new task families

1. Add `templates/sql/<area>/<name>.yaml` (id `sql.<area>.<name>`, version 1).
2. Pick `row_kind`s the fixture generator knows (`customers`, `orders`,
   `products`, `order_items`, `events`, `funnel_events`, `generic`) or extend
   `fixtures.py` with a new deterministic generator.
3. Use only `KNOWN_EDGE_CASES` vocabulary (extend it + add injection support
   together if a new case is needed).
4. Add the template to `configs/task_catalog.yaml`.
5. Run `pytest` — per-template parametrized tests cover the new file
   automatically.

## 11. Testing strategy

Invariants over execution: FK validity across all templates, fixture↔schema
agreement, DuckDB materialization + row counts, edge-case *evidence* (not
just declarations), serialization round-trips (model-stable), canonical
equality same-seed, independence across a 7-seed set incl. 0 and 2⁶³−1,
100-task catalog uniqueness + recreatability, task-id input sensitivity,
per-family semantic keys with ambiguity rejection.
See `tests/`.

## 12. Known limitations

- Row volumes are laptop-small (tens of rows); scale-up is Phase 7 work.
- `empty_result` is intentionally not fixture-evidenced: no Phase 1 template
  declares it; empty-result coverage belongs to Phase 4 hidden tests.
- No empirical difficulty calibration yet — difficulty is template-declared
  (1–5), not benchmarked.
- Logical replay is guaranteed per `ENGINE_VERSION`; the surrounding
  environment (Python, deps) still needs pinning — full environment locking
  is Phase 6 provenance work (see `docs/phase-1-contract.md`).

## 13. Frozen contract

`docs/phase-1-contract.md` (inputs, outputs, guarantees, Phase 2 `api`
surface) and `docs/task-semantics.md` (per-family oracle reference) are the
frozen Phase 1 deliverables alongside this document.
