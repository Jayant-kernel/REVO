# Stage 1 acceptance amendment

This append-only amendment resolves the actionable ambiguities found by the
cold challenge of `AGENCY-SPEC-FROZEN-20261007.md`. It narrows no frozen rubric
criterion and changes no historical artifact.

## Population

Stage 1 covers every current production `(template_id, template_version)` in
the builtin registry and every oracle implementation reachable from those
entries. Retired versions remain replayable and must fail closed, but they do
not enlarge current-catalog scoring denominators.

## Type authority

`ExpectedResult.column_types`, produced by the versioned oracle, is the sole
expected output-type authority for comparison. It must contain exactly one
declared type per output column even when `rows` is empty. Candidate/database
metadata is evidence about the actual output only: it may demonstrate a type
contract mismatch, but it may never select the coercion used for expected
values or supply a missing expected schema.

The mandatory supported scalar families are signed and unsigned integers,
fixed-point decimal/numeric, floating point, character text, boolean, date,
timestamp, and time. Types outside the declared supported matrix fail closed.
Supporting these families does not imply support for every database-specific
container, interval, timezone, or nested type.

## Result semantics

An unordered contract compares a bag: row order is ignored and duplicate
multiplicity is preserved. An ordered contract must first satisfy its declared
ordering keys, directions, and NULL placement, then must equal the expected bag.
Expected row-list position is not an additional order contract. Exact integer
and decimal families are exact; only declared floating output uses configured
floating tolerance. Null equals only null.

## Version and evidence rules

Changing a previously untyped or candidate-inferred path to an authoritative
schema changes verification semantics and therefore advances that registry
entry's oracle implementation version. Source-bound qualification evidence for
an advanced entry becomes stale and must be replayed; it cannot be relabelled.
No human re-adjudication path is available in this campaign.

The Stage 1 certificate must identify current contract/oracle versions, source
and dependency hashes, nonempty population and check counts, execution failure
count, focused command results, frozen-lock/guard results, and freshness status.
A bare PASS label cannot satisfy Stage 1.

## Stage 1 exit

Every current production oracle path has a complete authoritative schema for
empty and nonempty results. Adversarial tests cover cross-family candidate type
claims, mandatory supported families, unsupported types, malformed schemas,
exact numeric boundaries, temporal normalization, NULL ordering, ordered versus
unordered bags, and duplicate multiplicity. Changed entries are versioned and
dependent evidence is explicitly stale or freshly replayed. Independent cold
verification must pass before Stage 2 begins.
