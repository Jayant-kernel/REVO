# Golden Record (conceptual) — Verified SQL Data Factory

Status: **Phase 0 — schema sketch. Exact implementation refined in Phases 5–7.**

One final verified dataset record is expected to contain, conceptually:

```json
{
  "task": {},
  "instruction": "",
  "schema": {},
  "fixture": {},
  "candidate_solution": "",
  "verification": {},
  "quality": {},
  "provenance": {}
}
```

## Field notes

- **task** — task id, TaskVersion id, family (e.g. `window_functions`),
  difficulty, template version. Links to the authoritative task spec
  (spec > natural-language prompt; see ADR-005).
- **instruction** — the exact natural-language instruction shown to the model.
- **schema** — the SQL schema (DDL / column types) the solution runs against.
- **fixture** — fixture reference + seed + deterministic recreation info
  (tables, row counts, edge cases covered).
- **candidate_solution** — normalized verified SQL text (+ parse metadata).
- **verification** — verdict + evidence: oracle comparison, public/hidden/
  property/metamorphic results, mutation score of the suite, performance
  check, container digest, test-suite version.
- **quality** — deduplication outcome, difficulty/coverage contribution,
  ambiguity flags, human-audit status.
- **provenance** — model + revision, prompt version, oracle version,
  timestamps, dataset version, license references. Must allow full
  reproduction (see ADR-006).

## Chain-of-Thought policy (see ADR-007)

- Chain-of-Thought is **NOT** a mandatory core field.
- The value proposition is verified correctness, not private reasoning traces.
- A concise `explanation` / rationale field may be added later as optional
  metadata if it proves useful — never as a substitute for executable evidence.
