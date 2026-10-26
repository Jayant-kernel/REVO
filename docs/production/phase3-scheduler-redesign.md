# Phase 3 Scheduler Redesign

## Compatibility

`legacy` is the default scheduling mode. It preserves the existing family
rotation, seed calculation, and template selection byte-for-byte. Frozen
production configurations remain in `legacy` mode and are not edited.

## Distinct Contract Mode

`distinct_contract` is an opt-in configuration mode. A contract ID is the
stable task-template ID. The configuration supplies selected contract IDs for
every family. Each batch assigns a distinct selected contract to each task and
never repeats a contract within a family.

When a family selects more contracts than it schedules, the scheduler applies
the configured `contract_id_ascending` rule: IDs are sorted lexically and the
first scheduled count is used. Contract ID is therefore the deterministic tie
break, independent of registry load order.

## Preflight

Distinct mode fails closed before a run writes artifacts when a selected ID is
unknown, belongs to a different family, is repeated, provides fewer contracts
than the scheduled family count, or is not fully verified. Verification status
comes from an injectable readiness callback because the production scheduler
does not own verification evidence. Without that callback, distinct mode is
not ready to run.

The semantic-duplicate gate is unchanged: its denominator remains distinct
task IDs rather than generated sibling candidates.
