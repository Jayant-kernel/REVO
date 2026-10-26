"""New private challenge evidence; never overwrite the historical corpus."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_business_tasks import SAAS_V2_CHAINED_JOIN_SQL as JOIN_SQL
from tests.test_saas_v2_differential_sql import RECURSIVE_SQL
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.adversarial import independent_adversarial_tables
from verified_data_factory.verification.oracle_registry import get_oracle


def catalog() -> dict[str, str]:
    variants = {
        "count_vs_sum": JOIN_SQL.replace("SUM(p.amount)", "COUNT(p.amount)"),
        "last_payment": JOIN_SQL.replace("ORDER BY p.occurred_at, p.sequence", "ORDER BY p.occurred_at DESC, p.sequence DESC"),
        "wrong_tie_direction": JOIN_SQL.replace("ORDER BY p.occurred_at, p.sequence", "ORDER BY p.occurred_at, p.sequence DESC"),
        "missing_year": JOIN_SQL.replace("EXTRACT(YEAR FROM occurred_at)=2025", "TRUE"),
        "missing_zero_group": JOIN_SQL.replace("LEFT JOIN payments", "JOIN payments"),
        "outside_groups": JOIN_SQL.replace("SELECT DISTINCT group_key FROM scoped", "SELECT DISTINCT group_key FROM account_funnel"),
        "skipped_trial": JOIN_SQL.replace("t.status = 'trial'", "t.status IN ('trial','activation')"),
        "bad_entity_join": JOIN_SQL.replace("p.entity_id = a.entity_id", "TRUE"),
        "hardcoded_output": "SELECT 'fixed' AS group_key, 0 AS total_amount",
        "wrong_grouping": JOIN_SQL.replace("SELECT DISTINCT group_key FROM scoped", "SELECT DISTINCT group_key, entity_id FROM scoped").replace("GROUP BY s.group_key ORDER", "GROUP BY s.group_key, s.entity_id ORDER"),
        "unmatched_amount": JOIN_SQL.replace("p.status = 'payment'", "p.status IN ('payment','cancelled')").replace("AND status IN ('signup','trial','activation','payment')", ""),
        "all_events_amount": "SELECT group_key, SUM(amount) AS total_amount FROM account_funnel GROUP BY group_key ORDER BY group_key",
        "wrong_order": JOIN_SQL.replace("ORDER BY s.group_key ASC", "ORDER BY s.group_key DESC"),
        "null_total": JOIN_SQL.replace("COALESCE(SUM(p.amount), 0)", "SUM(p.amount)"),
        "all_payments": JOIN_SQL.replace("SELECT * FROM payment_candidates WHERE step_rn = 1", "SELECT * FROM payment_candidates"),
        "average_amount": JOIN_SQL.replace("SUM(p.amount)", "AVG(p.amount)"),
        "maximum_amount": JOIN_SQL.replace("SUM(p.amount)", "MAX(p.amount)"),
        "minimum_amount": JOIN_SQL.replace("SUM(p.amount)", "MIN(p.amount)"),
        "year_2024": JOIN_SQL.replace("occurred_at)=2025", "occurred_at)=2024"),
        "year_2026": JOIN_SQL.replace("occurred_at)=2025", "occurred_at)=2026"),
        "premature_payment": JOIN_SQL.replace("(p.occurred_at, p.sequence) > (a.occurred_at, a.sequence)", "TRUE"),
        "reset_unrelated": RECURSIVE_SQL.replace("ELSE w.progress END", "ELSE 0 END"),
    }
    return variants


def main() -> None:
    task = generate_task(load_builtin_registry().get("sql.funnel.saas_activation_payment", 2), 1)
    oracle = get_oracle(task.template_id, task.template_version).fn
    rows = []
    patterns = [
        (1, "a", 2025, ["signup", "trial", "activation", "payment", "payment"]),
        (2, "a", 2025, ["payment", "signup", "trial", "activation", "payment"]),
        (3, "b", 2025, ["signup"]),
        (4, "c", 2024, ["signup", "trial", "activation", "payment"]),
        (5, "d", 2026, ["signup", "trial", "activation", "payment"]),
        (6, "b", 2025, ["signup", "activation", "payment"]),
        (7, "a", 2025, ["signup", "trial", "trial", "activation", "cancelled", "payment"]),
        (8, "e", 2025, ["signup", "activation", "activation", "payment"]),
    ]
    for entity, group, year, steps in patterns:
        for seq, step in enumerate(steps, 1):
            rows.append({"record_id": len(rows) + 1, "entity_id": entity,
                         "group_key": group, "occurred_at": f"{year}-02-01 00:00:00",
                         "sequence": seq, "status": step, "amount": entity * 10 + seq})
    fixtures = [{"account_funnel": rows}, independent_adversarial_tables(task)]
    results = []
    for name, sql in catalog().items():
        record = {"name": name, "sql": sql, "classification": "UNRESOLVED"}
        for tables in fixtures:
            if tables is None:
                continue
            expected = oracle(task.requirements, tables)
            connection = materialize_duckdb(task.schema_, tables)
            try:
                cursor = connection.execute(sql)
                actual = [list(row) for row in cursor.fetchall()]
                if actual != expected.rows:
                    record.update(classification="KILLED_WRONG_ANSWER", witness=tables,
                                  expected=expected.rows, actual=actual)
                    break
            except duckdb.Error as exc:
                record.update(classification="EXECUTION_ERROR", error=str(exc))
                break
            finally:
                connection.close()
        results.append(record)
    output = ROOT / "scratch/funnel_experiment/evidence/challenge-repair-private.json"
    payload = {"lineage": "differential verification; repair of insufficient Phase 5 evidence",
               "excluded_from": ["prompts", "feedback", "training", "model-visible logs"],
               "queries": results, "semantic_kills": sum(r["classification"] == "KILLED_WRONG_ANSWER" for r in results)}
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"semantic_kills": payload["semantic_kills"],
                      "unresolved": [r["name"] for r in results if r["classification"] != "KILLED_WRONG_ANSWER"],
                      "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
