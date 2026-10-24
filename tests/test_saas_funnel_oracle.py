"""Focused semantic tests for the versioned SaaS activation-payment contract."""

import pytest

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.oracle_registry import get_oracle


def _row(
    record_id: int,
    entity_id: int,
    status: str,
    sequence: int,
    amount: int = 0,
    group: str = "north",
    occurred_at: str = "2025-01-01 00:00:00",
) -> dict[str, object]:
    return {
        "record_id": record_id,
        "entity_id": entity_id,
        "group_key": group,
        "occurred_at": occurred_at,
        "status": status,
        "amount": amount,
        "sequence": sequence,
    }


def _evaluate(rows: list[dict[str, object]]) -> list[list[object]]:
    task = generate_task(load_builtin_registry().get("sql.funnel.saas_activation_payment"), 1)
    return (
        get_oracle(task.template_id, task.template_version)
        .fn(task.requirements, {"account_funnel": rows})
        .rows
    )


def test_same_timestamp_reverse_input_uses_sequence() -> None:
    rows = [
        _row(4, 1, "payment", 4, 7),
        _row(3, 1, "activation", 3),
        _row(2, 1, "trial", 2),
        _row(1, 1, "signup", 1),
    ]
    assert _evaluate(rows) == [["north", 7]]


def test_out_of_order_trial_is_ignored_then_later_trial_completes() -> None:
    rows = [
        _row(1, 1, "trial", 1),
        _row(2, 1, "signup", 2),
        _row(3, 1, "trial", 3),
        _row(4, 1, "activation", 4),
        _row(5, 1, "payment", 5, 8),
    ]
    assert _evaluate(rows) == [["north", 8]]


def test_repeated_payment_uses_first_matched_payment() -> None:
    rows = [
        _row(1, 1, "signup", 1),
        _row(2, 1, "trial", 2),
        _row(3, 1, "activation", 3),
        _row(4, 1, "payment", 4, 7),
        _row(5, 1, "payment", 5, 99),
    ]
    assert _evaluate(rows) == [["north", 7]]


def test_skipped_step_never_completes() -> None:
    assert _evaluate(
        [_row(1, 1, "signup", 1), _row(2, 1, "activation", 2), _row(3, 1, "payment", 3, 9)]
    ) == [["north", 0]]


def test_early_payment_is_ignored_then_later_payment_counts() -> None:
    rows = [
        _row(1, 1, "signup", 1),
        _row(2, 1, "payment", 2, 99),
        _row(3, 1, "trial", 3),
        _row(4, 1, "activation", 4),
        _row(5, 1, "payment", 5, 11),
    ]
    assert _evaluate(rows) == [["north", 11]]


def test_2024_signup_does_not_start_2025_completion() -> None:
    rows = [
        _row(1, 1, "signup", 1, occurred_at="2024-12-31 23:59:59"),
        _row(2, 1, "trial", 2),
        _row(3, 1, "activation", 3),
        _row(4, 1, "payment", 4, 10),
    ]
    assert _evaluate(rows) == [["north", 0]]


def test_never_completing_entity_returns_zero() -> None:
    assert _evaluate([_row(1, 1, "signup", 1)]) == [["north", 0]]


def test_in_scope_zero_completion_segment_returns_zero() -> None:
    assert _evaluate([_row(1, 1, "signup", 1, group="south")]) == [["south", 0]]


def test_segment_without_in_scope_rows_is_absent() -> None:
    assert _evaluate([_row(1, 1, "cancelled", 1)]) == []


def test_cancelled_rows_are_ignored() -> None:
    rows = [
        _row(1, 1, "signup", 1),
        _row(2, 1, "cancelled", 2, 99),
        _row(3, 1, "trial", 3),
        _row(4, 1, "activation", 4),
        _row(5, 1, "payment", 5, 3),
    ]
    assert _evaluate(rows) == [["north", 3]]


def test_groups_are_sorted_ascending() -> None:
    rows = [_row(1, 1, "signup", 1, group="z"), _row(2, 2, "signup", 1, group="a")]
    assert _evaluate(rows) == [["a", 0], ["z", 0]]


def test_group_key_constancy_including_out_of_scope_row_is_rejected() -> None:
    with pytest.raises(ValueError, match="one group_key"):
        _evaluate(
            [_row(1, 1, "signup", 1, group="north"), _row(2, 1, "cancelled", 2, group="south")]
        )


def test_metamorphic_shuffle_record_id_cancelled_and_out_of_scope_rows() -> None:
    base = [
        _row(1, 1, "signup", 1),
        _row(2, 1, "trial", 2),
        _row(3, 1, "activation", 3),
        _row(4, 1, "payment", 4, 7),
    ]
    changed = list(reversed(base)) + [
        _row(99, 1, "cancelled", 5, 999),
        _row(100, 1, "other", 6, 999),
    ]
    for index, row in enumerate(changed, start=1000):
        row["record_id"] = index
    assert _evaluate(base) == _evaluate(changed) == [["north", 7]]


def test_metamorphic_unmatched_amount_has_no_effect_and_matched_amount_changes_total() -> None:
    base = [
        _row(1, 1, "signup", 1, 1),
        _row(2, 1, "trial", 2, 2),
        _row(3, 1, "activation", 3, 3),
        _row(4, 1, "payment", 4, 7),
    ]
    unmatched_changed = [dict(row) for row in base]
    unmatched_changed[0]["amount"] = 999
    matched_changed = [dict(row) for row in base]
    matched_changed[-1]["amount"] = 12
    assert _evaluate(unmatched_changed) == [["north", 7]]
    assert _evaluate(matched_changed) == [["north", 12]]


def test_metamorphic_disjoint_entities_combine_and_group_rename_preserves_totals() -> None:
    first = [
        _row(1, 1, "signup", 1),
        _row(2, 1, "trial", 2),
        _row(3, 1, "activation", 3),
        _row(4, 1, "payment", 4, 7),
    ]
    second = [
        _row(5, 2, "signup", 1, group="south"),
        _row(6, 2, "trial", 2, group="south"),
        _row(7, 2, "activation", 3, group="south"),
        _row(8, 2, "payment", 4, 9, group="south"),
    ]
    assert _evaluate(first + second) == [["north", 7], ["south", 9]]
    renamed = [dict(row, group_key="west") for row in first]
    assert _evaluate(renamed) == [["west", 7]]


def test_saas_rejects_duplicate_entity_occurred_at_sequence() -> None:
    task = generate_task(load_builtin_registry().get("sql.funnel.saas_activation_payment"), 1)
    rows = [
        {
            "record_id": 1,
            "entity_id": 1,
            "group_key": "north",
            "occurred_at": "2025-01-01 00:00:00",
            "status": "signup",
            "amount": 0,
            "sequence": 1,
        },
        {
            "record_id": 2,
            "entity_id": 1,
            "group_key": "north",
            "occurred_at": "2025-01-01 00:00:00",
            "status": "trial",
            "amount": 0,
            "sequence": 1,
        },
    ]
    oracle = get_oracle(task.template_id, task.template_version)
    with pytest.raises(ValueError, match="unique occurred_at and sequence"):
        oracle.fn(task.requirements, {"account_funnel": rows})
