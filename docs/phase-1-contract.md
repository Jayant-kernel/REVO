# Phase 1 Contract (frozen)

The Task Engine is a deterministic function from versioned inputs to a
validated `TaskInstance`. Phase 2 programs against `task_engine.api` only.

## Input

```text
template            # TaskTemplate loaded from templates/sql/**/*.yaml
template version    # int, immutable once published (never silently mutate v1)
generation config   # template.generation_config (+ optional override)
seed                # non-negative int
engine version      # ENGINE_VERSION = "1.0.0"
```

## Output

`TaskInstance` with required fields:

```text
task_id               # {template_id}.v{version}.{12-hex identity hash}
template_id           # e.g. sql.retention.30_day
template_version      # int
seed                  # int (full value; the id suffix is a hash, not the seed)
family                # e.g. retention
difficulty            # 1..5 (template-declared, NOT empirically calibrated)
instruction           # rendered natural language (spec is authoritative, ADR-005)
schema                # list of tables (canonical name-sorted; external key "schema")
tables                # fixture rows keyed by table
fixture_metadata      # engine=duckdb, seed, generation_version, row counts
requirements          # family semantic keys (see docs/task-semantics.md)
constraints           # from generation config
edge_cases            # ensured + sorted; each is fixture-evidenced (except
                      # `empty_result`, which is Phase-4-owned by design)
oracle_spec           # {type: reference_query, strategy} — metadata only
generation_metadata   # {engine_version, config}
```

## Determinism guarantee (logical reproducibility)

```text
same template ID + same template version + same generation config
+ same seed + same ENGINE_VERSION
= same canonical TaskInstance (canonical JSON + task_id identical)
```

`ENGINE_VERSION` names the behavior contract. It MUST be bumped (and the
break documented) when a change can alter: task semantics, fixture values,
row counts, edge-case injection, instruction rendering, validation
acceptance, or task identity. Within one `ENGINE_VERSION`, replay is exact —
verified by `recreate_task()` and the 100-task catalog replay test.

## Environment reproducibility (boundary)

Logical reproducibility assumes a compatible environment; it does NOT
extend across arbitrary dependency changes. Phase 1 boundary:

- Fixture randomness uses only stdlib `random`/`hashlib` (stable streams).
- DuckDB is used for materialization checks, not for fixture values —
  fixture rows are identical regardless of DuckDB version.
- Python `>=3.12` and the pinned `pyproject.toml` dependency set are
  required; full environment locking (lockfile, container digest) is
  Phase 6 provenance work, not Phase 1.

## Serialization guarantee

- JSON (`serialize_task`) and JSONL (`write_jsonl`/`read_jsonl`) are stable.
- External key is `"schema"` (internal attribute `schema_` avoids shadowing
  `BaseModel.schema`; no warnings emitted).
- Tables name-sorted, edge cases sorted: model-level round-trips are stable,
  i.e. `deserialize(serialize(t)) == t`.
- `validate_task` additionally binds `task_id` to the generation inputs —
  tampered ids are rejected.

## Non-responsibilities

The Task Engine does NOT: generate candidate SQL, judge candidate SQL,
execute candidates for verification, produce correctness verdicts, run
hidden/property/metamorphic/mutation tests, score quality, or track
provenance beyond per-task generation metadata.

## Phase 2 interface (`task_engine.api`)

```python
get_template(registry, template_id, version=None) -> TaskTemplate
list_templates(registry, family=None) -> list[TaskTemplate]
generate_task(template, seed, config_override=None) -> TaskInstance
generate_batch(template, seeds, config_override=None) -> list[TaskInstance]
validate_task(task) -> None  # raises ValidationError
serialize_task(task) -> str  # stable JSON
deserialize_task(text) -> TaskInstance  # reconstruct + validate
recreate_task(registry, task) -> TaskInstance  # replay-or-raise
recreate_fixture(template, seed) -> (tables, fixture_metadata)
```

Deeper modules (`fixtures`, `canonical`, `seed` internals) are available but
not contractual. No internal RNGs or mutable state are exposed. The CLI
(`factory task ...`) is a thin wrapper over this API.
