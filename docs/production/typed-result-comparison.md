# Typed result comparison

The verifier passes the sandbox's declared result-column types through every
comparison stage: visible, hidden, property, metamorphic, and mutation.
`compare(..., column_types=[...])` requires a type per output column, or an
explicit `ExpectedResult.column_types` contract. Absent/unknown types and
malformed values fail closed. If an expected type contract exists, execution
metadata cannot replace it with another type category.

Integers and decimals use exact arithmetic. Floating-point tolerance applies
only to declared floating columns; exact oracle integer/Decimal values do not
acquire a tolerance. Decimal strings are parsed only under a numeric column
contract; VARCHAR values are never interpreted as numbers. Scalar helper
compatibility uses native Python types, never text spelling.

Ordering follows declared types. Default NULL ordering is NULLS LAST for both
directions, and `OrderSpec.nulls` can state per-key FIRST/LAST explicitly.
Duplicate/unknown order columns are rejected. Temporal serialization is
normalized under explicit DATE/TIME/TIMESTAMP types.

Unordered outputs preserve multiplicity. Exact typed bags use counter equality;
floating bags use complete iterative augmenting-path matching, not greedy
matching. Ambiguous tolerance matches therefore cannot depend on row order.
Malformed rows are never dropped to make a result match.

Supported declared categories are integers, decimals, floats, text, booleans,
dates, times and timestamps. Unsupported complex types fail closed and need a
separately specified serialization/comparison contract before qualification.

Historical comparator-dependent certifications do not prove these new rules.
They are re-adjudicated separately from forward-version qualification in
engineering Phase 2. No historical candidate or frozen-run artifact is edited.

## Stage 1 semantic identity: 3.0-authoritative

Untyped `cells_equal` compares arbitrary Python integers exactly, without SQL
range limits or string conversion. An explicit SQL integer declaration still
enforces its signed/unsigned bounds. Native Decimal scalar equality is also
exact; it is not implicitly a bare SQL DECIMAL domain.

Declared DECIMAL/NUMERIC follows DuckDB domains: bare means `(18,3)`, `(p)`
means `(p,0)`, and `(p,s)` requires `1 <= p <= 38` and `0 <= s <= p`.
Values must be exactly representable without rounding: excess nonzero fractional
digits or magnitude at/above `10**(p-s)` fail. Trailing zeros do not consume
scale. Validation uses coefficient/exponent arithmetic, independent of Decimal
context precision. Integers, finite Decimal values and decimal strings (including
exponents) are accepted; floats retain their decimal `str` representation, not
the original pre-float precision. Floats cannot recover already lost digits.

Actual metadata must belong to the expected family. Same-family widths/scales
may differ only when every observed actual value is exactly representable in
both its declared actual domain and the expected domain; this is value-level
lossless compatibility, not a claim that the complete domains are interchangeable.
Empty results still validate both declarations. Floating tolerance never applies
to decimal values. Timezone-aware TIME/TIMESTAMP values, timezone type declarations,
intervals, blobs, JSON and nested/container types are unsupported and fail closed.

### Named historical replay caveats

The retired contracts `sql.aggregation.grouped@1`, `sql.cte.monthly@1`,
`sql.dedup.latest@1`, `sql.funnel.completion@1`, and `sql.temporal.monthly@1`
share implementations with current contracts. Their oracle implementation
identities now advance from 1 to 2 because those shared functions declare typed
schemas. Resolution remains supported for new re-adjudication, but does **not**
reproduce the historical v1 implementation or historical comparison semantics.
Old records/artifacts remain unchanged and cannot be relabelled as current proof.
All comparator-dependent qualifications require fresh execution under
`3.0-authoritative`. Top-category sales advances oracle 2 to 3 for its full
`total_sales DESC, category ASC` order contract. No manifests are promoted here.

### Stage 1 cold-challenge retry (round 2)

Explicit types are validated before scalar NULL equality: unsupported types,
malformed DECIMAL domains and empty type declarations fail even for NULL/NULL.
Untyped NULL/NULL remains equal. Native int/float and Decimal/float comparisons
are exact Python numeric equality, not integer-to-float or float-to-string
coercion. Thus `3 == 3.0`, but `float(2**53)` differs from `2**53 + 1`, and
`Decimal('0.1')` differs from the exact binary value of float `0.1`.
Configured floating tolerance still applies to native float/float pairs and
explicit declared floating outputs such as DOUBLE.

`sql.windows.ranked@1` retains its required `customer_id, order_date` OrderSpec
even though the frozen public projection omits order_date. Comparison refuses
proof of that order rather than silently dropping the key; both original and
reversed same-customer outputs fail closed. No historical projection was changed.
The latest `sql.windows.ranked@2` projects its date/order-id keys and remains
usable. Round-2 execution evidence is append-only in
`scratch/funnel_experiment/engineering/STAGE1-ROUND2-REPAIR-20261007.md`.
