# Phase 2 — Candidate Generation

Status: **implemented**. Takes a frozen Phase 1 `TaskInstance` and asks an
open-weight coding model for candidate SQL. Answers only *"what did the
model generate?"* — never *"is it correct?"* (Phase 4). No SQL is executed
here; no reference answers, oracles, or verdicts exist in this layer.

## 1. Generation architecture

```text
TaskInstance (task_engine.api — frozen, never mutated)
        │ build_solver_context / build_sql_prompt (prompt.py)
        ▼
SolverContext {task_id, dialect, ddl, instruction, requirements}
        │ Provider.generate(prompt, generation_config)
        ▼
GenerationResponse {raw_text, model, revision, finish, tokens, ms}
        │ extract_candidate_sql (parser.py)
        ▼
CandidateSolution (+ GenerationResult wrapper)
```

Modules: `models` (CandidateSolution, GenerationResponse, GenerationConfig,
TokenUsage, versions), `prompt`, `parser`, `provider`
(`Provider` ABC + `OpenAICompatibleProvider`), `providers/` (`qwen`,
`devstral`, registry + `create_provider`), `generator` (single/multi/batch
orchestration + candidate identity), `config` (endpoint + sampling settings),
`fake` (test-only `FakeProvider`), `export` (JSON/JSONL), `errors`
(transient vs permanent vs parse failures), `api` (public surface).

## 2. Provider interface

```python
provider.generate(prompt=prompt, generation_config=config) -> GenerationResponse
```

Downstream code sees only `Provider`. `OpenAICompatibleProvider` posts to
`{base_url}/chat/completions` (vLLM-style self-hosted servers) with
configurable endpoint/model/timeout/retries — vLLM is *a* compatible
runtime, never an assumption. No proprietary APIs exist anywhere.

## 3. Prompt construction

`build_solver_context(task)` builds a fresh object containing ONLY
instruction, DuckDB dialect, DDL, and explicit requirements. `oracle_spec`,
fixture rows, verification metadata, and task-engine internals are
structurally unreachable (not attributes of the context). `build_sql_prompt`
renders deterministically and demands SQL-only output (no fences, prose, or
comments) for reliable parsing.

## 4. Public solver context

See `SolverContext` in `prompt.py`. A dedicated leakage test asserts prompts
contain instruction/schema/dialect/requirements and exclude oracle text,
fixture cell values, and verification details.

## 5. Parser behavior

Extract-only: one fenced block → use it; multiple fenced blocks → `failed`
(ambiguous, never guess); no fence → strip leading prose to first
SELECT/WITH line, strip one trailing semicolon; anything else → `failed`
with an explicit reason (`empty_response`, `no_sql_found`,
`ambiguous_multiple_blocks`, `fenced_block_not_sql`). `raw_response` is
always preserved alongside `candidate_sql`.

## 6. CandidateSolution schema

`candidate_id` (`{task_id}.{model-slug}.{index}.{12-hex metadata hash}`),
`task_id`, `model`, `model_revision`, `prompt_version` (`sql-v1`),
`generation_schema_version` (`1.0`), `provider`, `endpoint_id`
(hash of provider/model/URL — no secrets), `candidate_index`,
`raw_response`, `candidate_sql` (nullable), `generation_config`,
`generation_timestamp`, `generation_duration_ms`, `finish_reason`,
`token_usage`, `provider_metadata`, `generation_status`, `parse_status`,
`failure_reason`. No correctness fields exist — asserted by test.

## 7. Generation configuration

`GenerationConfig{temperature=0.4, top_p=0.95, max_tokens=2048, seed=None}` —
only parameters the provider supports, defaults explicit. Endpoint settings
(`ProviderEndpoint`: base URL, env-only API key, timeout, retries) load from
YAML (`configs/generation_example.yaml`); sampling semantics across
backends are not claimed identical.

## 8. Multiple candidate generation

`generate_candidates(task, providers, config, num)` and
`generate_for_tasks(tasks, providers, config, num)`; per-(task, provider,
index) independence, failures isolated as `GenerationResult` data, order
preserved, no global state (parallelizable later; sequential now).

## 9. Retry behavior

`max_retries` (default 2) + exponential backoff for transient failures only
(timeout, connection error, 429, 5xx). Permanent failures (other 4xx,
malformed responses) raise immediately. Parse failures are never retried —
different failure class. Timeouts explicit and configurable.

## 10. Failure classes

`provider_failed` (network/model-side, retryable or not) vs `parse failed`
(model produced unusable output). Both surface as `GenerationResult` with
`failure_reason`; batches continue.

## 11. Provenance

Every candidate records task/model/revision/prompt-version/config/provider/
endpoint-id/index/timestamp. Raw output preserved. Secrets never stored
(API key stays in process env; endpoint identified by hash).

## 12. Testing strategy

`FakeProvider` (scripted outputs/errors, call log) drives everything offline:
prompt include/exclude, parser matrix, provider success/timeout/transient/
permanent/malformed/retry-limit, candidate binding + provenance + identity,
batch partial-failure + ordering, JSON/JSONL round-trips. No model download.

## 13. Phase 3 consumption

Sandbox receives `CandidateSolution.candidate_sql` + the TaskInstance's
fixture info (`schema`, `fixture_metadata`, seed/config for recreation).
Phase 4 receives `CandidateSolution` + `TaskInstance` and judges
independently. Candidates carry nothing either phase must unlearn.
