# SaaS v2 Rule-to-Evidence Matrix

| Rule | Type | Instruction / requirement | Positive evidence | Counterexample / breakage |
| --- | --- | --- | --- | --- |
| Scope year is 2025 | Query behavior | `year` | business fixtures | out-of-year signup case |
| Ordered steps | Query behavior | `funnel_steps`, `consecutiveness` | business fixtures | skipped step |
| Sequence breaks same-time ties | Query behavior | `same_timestamp_policy` | adversarial fixture | reverse order mutation |
| First matching step advances | Query behavior | `repeat_policy` | business fixture | last-payment mutation |
| Unmatched rows do not reset | Query behavior | instruction | business fixture | reset mutation |
| Payment amount only | Query behavior | `completion_amount` | business fixture | sum-all mutation |
| In-scope zero groups returned | Query behavior | instruction | business fixture | omit-zero mutation |
| One group per entity | Data guarantee | instruction | oracle validation | cross-group invalid input |
| Unique occurred_at/sequence | Data guarantee | `tie_uniqueness` | fixture validation | `test_saas_rejects_duplicate_entity_occurred_at_sequence` |
| Ascending output | Query behavior | `order_by` | comparator/order contract | ordering mutant |

Oracle imports only `collections`, `datetime`, `itertools`, `typing`, and local
result models. It imports no SQL, fixtures, candidates, expected-output tests, or
challenge data. Classification: differential verification; independence unproven.
Independent authorship deferred.

## Focused Test Inventory

- `test_same_timestamp_reverse_input_uses_sequence`: named case.
- `test_out_of_order_trial_is_ignored_then_later_trial_completes`: named case.
- `test_repeated_payment_uses_first_matched_payment`: named case.
- `test_skipped_step_never_completes`: named case.
- `test_early_payment_is_ignored_then_later_payment_counts`: named case.
- `test_2024_signup_does_not_start_2025_completion`: named case.
- `test_never_completing_entity_returns_zero`: named case.
- `test_in_scope_zero_completion_segment_returns_zero`: named case.
- `test_segment_without_in_scope_rows_is_absent`: named case.
- `test_cancelled_rows_are_ignored`: named case.
- `test_groups_are_sorted_ascending`: named case.
- `test_group_key_constancy_including_out_of_scope_row_is_rejected`: invalid-input.
- `test_saas_rejects_duplicate_entity_occurred_at_sequence`: invalid-input.
- `test_metamorphic_shuffle_record_id_cancelled_and_out_of_scope_rows`: metamorphic.
- `test_metamorphic_unmatched_amount_has_no_effect_and_matched_amount_changes_total`: metamorphic.
- `test_metamorphic_disjoint_entities_combine_and_group_rename_preserves_totals`: metamorphic.
