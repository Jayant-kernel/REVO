# Verification Principles — Verified SQL Data Factory

Status: **Phase 4 — implemented per these principles. See
`docs/phase-4-verification.md` for the as-built engine.**

## Principle 1 — Untrusted output

LLM-generated output is untrusted until verified. No candidate enters a
dataset on the basis of fluency, plausibility, or model confidence.

## Principle 2 — Executable over LLM-judged

LLM-as-judge must not be the primary correctness mechanism when executable
verification is possible. For SQL, correctness is decided by running queries
against fixtures and comparing against an independent oracle plus tests —
not by asking another model whether the SQL "looks right".

## Principle 3 — Public tests are insufficient

Public (visible) tests guide generation but cannot certify correctness;
candidates can overfit to them. Public-test passage is a filter, not a verdict.

## Principle 4 — Hidden tests are required

Every TaskVersion ships a hidden test set that candidates never see during
generation: held-out fixtures, edge cases (NULLs, ties, duplicates,
empty inputs, boundary dates), and alternative valid orderings/semantics.

## Principle 5 — Property-based testing where applicable

Use property tests (e.g. Hypothesis in later phases) for invariants:
row-count bounds, idempotence of dedup, grouping consistency, join
cardinality, monotonicity of window results, etc.

## Principle 6 — Metamorphic testing where applicable

Use metamorphic relations: equivalent query rewrites, row-order permutations
(where order-insensitive), predicate pushdown variants, and fixture
transformations must preserve the expected result.

## Principle 7 — Mutation testing measures suite strength

Mutation testing quantifies whether the test suite can actually catch bugs:
seed faulty SQL variants and require the suite to kill them. A high pass
rate against a weak suite is not verification.

## Principle 8 — Performance matters

Functional correctness plus a performance gate: runaway queries
(cartesian explosions, missing join predicates) fail even if logically
correct. Record timing in every VerificationRun.

## Principle 9 — Task quality ≠ solution correctness

Task quality is evaluated separately: is the instruction unambiguous, is the
fixture discriminating, does the task cover the intended skill? A correct
solution to a bad task still produces a bad record.

## Principle 10 — Reproducibility

Every Golden example must be reproducible: task-template version + fixture
seed + oracle version + test-suite version + container digest must recreate
the verdict bit-for-bit (see ADR-006).
