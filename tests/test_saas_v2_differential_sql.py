"""Differential proof for the authoritative SaaS v2 non-recursive SQL."""

from __future__ import annotations

import random
from datetime import date, datetime

import pytest

from tests.test_business_tasks import SAAS_V2_CHAINED_JOIN_SQL
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.adversarial import independent_adversarial_tables
from verified_data_factory.verification.oracle_registry import get_oracle

RECURSIVE_SQL = """WITH RECURSIVE scoped AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY entity_id ORDER BY occurred_at, sequence) AS rn
    FROM account_funnel WHERE EXTRACT(YEAR FROM occurred_at)=2025
      AND status IN ('signup','trial','activation','payment')
), walk AS (
    SELECT entity_id, group_key, rn, amount, CASE WHEN status='signup' THEN 1 ELSE 0 END AS progress,
      CAST(NULL AS INTEGER) AS matched_amount FROM scoped WHERE rn=1
    UNION ALL
    SELECT s.entity_id, s.group_key, s.rn, s.amount,
      CASE WHEN w.progress < 4 AND s.status=CASE w.progress WHEN 0 THEN 'signup' WHEN 1 THEN 'trial' WHEN 2 THEN 'activation' WHEN 3 THEN 'payment' END THEN w.progress+1 ELSE w.progress END,
      CASE WHEN w.progress=3 AND s.status='payment' THEN s.amount ELSE w.matched_amount END
    FROM walk w JOIN scoped s ON s.entity_id=w.entity_id AND s.rn=w.rn+1
), completed AS (
    SELECT entity_id, MAX(group_key) AS group_key, MAX(progress) AS progress, MAX(matched_amount) AS matched_amount
    FROM walk GROUP BY entity_id
), segments AS (SELECT DISTINCT group_key FROM scoped)
SELECT s.group_key, COALESCE(SUM(CASE WHEN c.progress=4 THEN c.matched_amount ELSE 0 END), 0) AS total_amount
FROM segments s LEFT JOIN completed c ON c.group_key=s.group_key
GROUP BY s.group_key ORDER BY s.group_key ASC"""

MUTANTS = {
    "wrong_year": SAAS_V2_CHAINED_JOIN_SQL.replace("occurred_at)=2025", "occurred_at)=2024"),
    "trial_starts_funnel": SAAS_V2_CHAINED_JOIN_SQL.replace("status = 'signup'", "status = 'trial'", 1),
    "all_payments_count": SAAS_V2_CHAINED_JOIN_SQL.replace("SELECT * FROM payment_candidates WHERE step_rn = 1", "SELECT * FROM payment_candidates"),
}


def _task():
    return generate_task(load_builtin_registry().get("sql.funnel.saas_activation_payment"), 1)


def _execute(tables, sql):
    task = _task()
    connection = materialize_duckdb(task.schema_, tables)
    try:
        return [[str(value) if isinstance(value, (date, datetime)) else value for value in row]
                for row in connection.execute(sql).fetchall()]
    finally:
        connection.close()


def _oracle(tables):
    task = _task()
    return get_oracle(task.template_id, task.template_version).fn(task.requirements, tables).rows


def _fuzz_tables(seed: int):
    rng = random.Random(seed)
    rows = []
    record_id = 1
    for entity_id in range(1, rng.randint(2, 7)):
        group = ("north", "south", "west")[entity_id % 3]
        for sequence in range(1, rng.randint(2, 9)):
            rows.append({
                "record_id": record_id, "entity_id": entity_id, "group_key": group,
                "occurred_at": f"{rng.choice((2024, 2025, 2026))}-01-{sequence:02d} 00:00:00",
                "status": rng.choice(("signup", "trial", "activation", "payment", "cancelled")),
                "amount": rng.randint(0, 100), "sequence": sequence,
            })
            record_id += 1
    rng.shuffle(rows)
    return {"account_funnel": rows}


def test_named_fixture_agrees_across_oracle_recursive_and_chained_join() -> None:
    task = _task()
    tables = independent_adversarial_tables(task)
    assert tables is not None
    expected = _oracle(tables)
    assert expected == [["east", 11], ["north", 0], ["west", 7], ["zero", 0]]
    assert _execute(tables, RECURSIVE_SQL) == expected
    assert _execute(tables, SAAS_V2_CHAINED_JOIN_SQL) == expected


@pytest.mark.parametrize("seed", range(40))
def test_fuzz_agrees_across_oracle_recursive_and_chained_join(seed: int) -> None:
    tables = _fuzz_tables(seed)
    expected = _oracle(tables)
    assert _execute(tables, RECURSIVE_SQL) == expected
    assert _execute(tables, SAAS_V2_CHAINED_JOIN_SQL) == expected


@pytest.mark.parametrize("name,mutant", MUTANTS.items())
def test_relevant_chained_join_mutants_are_killed(name: str, mutant: str) -> None:
    corpus = [_fuzz_tables(seed) for seed in range(40)]
    corpus.append({"account_funnel": [
        {"record_id": 1, "entity_id": 99, "group_key": "repeat", "occurred_at": "2025-01-01 00:00:00", "status": "signup", "amount": 0, "sequence": 1},
        {"record_id": 2, "entity_id": 99, "group_key": "repeat", "occurred_at": "2025-01-02 00:00:00", "status": "trial", "amount": 0, "sequence": 2},
        {"record_id": 3, "entity_id": 99, "group_key": "repeat", "occurred_at": "2025-01-03 00:00:00", "status": "activation", "amount": 0, "sequence": 3},
        {"record_id": 4, "entity_id": 99, "group_key": "repeat", "occurred_at": "2025-01-04 00:00:00", "status": "payment", "amount": 7, "sequence": 4},
        {"record_id": 5, "entity_id": 99, "group_key": "repeat", "occurred_at": "2025-01-05 00:00:00", "status": "payment", "amount": 99, "sequence": 5},
    ]})
    task = _task()
    named = independent_adversarial_tables(task)
    assert named is not None
    corpus.insert(0, named)
    assert any(_execute(tables, mutant) != _oracle(tables) for tables in corpus), name
