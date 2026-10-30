# Scratch Experiment Integration

1. Resolve a contract: `load_builtin_registry().get(contract_id)` returns a
   `TaskTemplate`; `generate_task(template, seed) -> TaskInstance` materializes
   its public instruction, schema, requirements, fixture rows, and identity.
2. Generate: `generate_candidate(task, provider, config, candidate_index=0) ->
   GenerationResult`. Its provider receives only `build_sql_prompt(task)`, which
   exposes public instruction, DDL, and requirements.
3. Execute: `ExecutionBackend.execute(task: TaskInstance, candidate:
   CandidateSolution) -> ExecutionResult`; production uses `executor.execute`.
4. Verify: `verify_candidate(task: TaskInstance, candidate: CandidateSolution,
   execution: ExecutionResult, config=None, backend=None) -> VerificationResult`.
   It needs the same task to obtain fixture/oracle inputs, but those never reach
   the generator prompt.
5. The adapter can call all three directly. It must construct its
   `CandidateSolution` through `generate_candidate`, rather than accepting a
   bare SQL string, so candidate identity/provenance and parsed SQL are valid.
6. Gap: the scratch adapter has not yet bound a real Ollama provider and
   execution backend to this path while preserving its append-only call key.
