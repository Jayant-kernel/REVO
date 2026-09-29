# Deterministic splitting

Splitting is a pure function of (record identity, split policy) —
no global RNG, no wall-clock, no filesystem order.

## Mechanism

1. Each record maps to an **isolation group** (`group_key_for`):
   - `semantic_group` (default): semantic duplicate group id, falling
     back to exact duplicate group id, else the bare candidate id.
   - `exact_group`: exact duplicate group id only.
   - `template`: the task's `template_id`.
   - `none`: every record is its own group.
2. Each group draws one variate: `SHA-256(seed | group key |
   representative id)` scaled to `[0, 1)`.
3. The variate is cut by the normalized `train / public_eval /
   private_eval` ratios. (`benchmark` is derived from the public_eval
   assignment at build time for `BENCHMARK` products.)
4. Every group — never an individual row — lands in exactly one split,
   so duplicate/semantic groups cannot straddle splits when
   `require_group_isolation` holds (verified by
   `verify_group_isolation`).

## Properties

- Same seed + same inputs → identical splits (tested twice-build).
- Different seeds → different (still valid) partitions.
- All-zero ratios and `min_split_size` violations raise
  `ProductConfigError` instead of shipping a degenerate plan.
- `balance_families` is a documented no-op unless family inputs are
  supplied — the policy keeps hash assignment rather than rebalancing
  silently.

## Product mapping

- `TRAIN` ships the `train` split; `PUBLIC_EVAL` ships `public_eval`;
  `PRIVATE_EVAL` ships `private_eval`; `BENCHMARK` ships the
  `public_eval` members relabeled `benchmark`; `SAMPLE` ships the first
  25 `train` records in candidate-id order.
