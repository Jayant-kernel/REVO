"""Edge-case representation tests: declared edge cases must actually be present.

For each template: declared edge case -> fixture generator -> real evidence
in the generated data. Metadata never claims what the fixture lacks.
"""

from collections import Counter
from itertools import pairwise

from verified_data_factory.task_engine import generate_task


def _has_none(rows) -> bool:
    return any(v is None for r in rows for v in r.values())


def test_simple_joins_edges(registry):
    task = generate_task(registry.get("sql.joins.simple"), seed=101)
    ordered = {r["customer_id"] for r in task.tables["orders"]}
    assert any(c["customer_id"] not in ordered for c in task.tables["customers"])
    assert _has_none(task.tables["customers"]) or _has_none(task.tables["orders"])


def test_multi_joins_edges(registry):
    task = generate_task(registry.get("sql.joins.multi"), seed=201)
    counts = Counter(r["customer_id"] for r in task.tables["orders"])
    assert any(v >= 2 for v in counts.values())  # multiple matching rows
    ordered = {r["customer_id"] for r in task.tables["orders"]}
    assert any(c["customer_id"] not in ordered for c in task.tables["customers"])


def test_aggregation_edges(registry):
    task = generate_task(registry.get("sql.aggregation.grouped"), seed=301)
    rows = task.tables["orders"]
    assert any(r["amount"] is None for r in rows)  # null_values
    assert any(r["amount"] == 0 for r in rows)  # zero_values
    assert any(v == 1 for v in Counter(r["status"] for r in rows).values())  # singleton


def test_windows_edges(registry):
    task = generate_task(registry.get("sql.windows.ranked"), seed=601)
    amounts = [r["amount"] for r in task.tables["orders"]]
    assert len(amounts) != len(set(amounts))  # ties
    assert _has_none(task.tables["customers"]) or _has_none(task.tables["orders"])


def test_temporal_edges(registry):
    task = generate_task(registry.get("sql.temporal.monthly"), seed=701)
    times = [e["event_time"] for e in task.tables["events"]]
    assert any(a > b for a, b in pairwise(times))  # out of order
    days = [t.split(" ")[0] for t in times]
    assert any(v >= 2 for v in Counter(days).values())  # same day


def test_dedup_edges(registry):
    task = generate_task(registry.get("sql.dedup.latest"), seed=801)
    rows = task.tables["events"]
    keys = [(r["customer_id"], r["event_type"], r["event_time"]) for r in rows]
    assert len(keys) != len(set(keys))  # real duplicate business key
    assert len({r["event_time"] for r in rows}) < len(rows)  # timestamp tie


def test_retention_edges(registry):
    task = generate_task(registry.get("sql.retention.30_day"), seed=901)
    events = task.tables["events"]
    customers = {c["customer_id"] for c in task.tables["customers"]}
    with_events = {e["customer_id"] for e in events}
    assert customers - with_events, "no customer without events"  # no_events
    keys = [(e["customer_id"], e["event_type"], e["event_time"]) for e in events]
    assert len(keys) != len(set(keys))  # duplicate_events
    purchases = Counter(e["customer_id"] for e in events if e["event_type"] == "purchase")
    assert any(v >= 2 for v in purchases.values())  # multiple_purchases
    days = [e["event_time"].split(" ")[0] for e in events]
    assert any(v >= 2 for v in Counter(days).values())  # same_day_events


def test_funnel_edges(registry):
    task = generate_task(registry.get("sql.funnel.completion"), seed=1001)
    events = task.tables["events"]
    customers = {c["customer_id"] for c in task.tables["customers"]}
    assert customers - {e["customer_id"] for e in events}  # missing relationships
    times = [e["event_time"] for e in events]
    assert any(a > b for a, b in pairwise(times))  # out of order
    keys = [(e["customer_id"], e["event_type"], e["event_time"]) for e in events]
    assert len(keys) != len(set(keys))  # duplicate_events


def test_cte_subquery_missing_relationships(registry):
    for tid, seed in [("sql.cte.monthly", 401), ("sql.subqueries.exists", 501)]:
        task = generate_task(registry.get(tid), seed=seed)
        ordered = {r["customer_id"] for r in task.tables["orders"]}
        assert any(c["customer_id"] not in ordered for c in task.tables["customers"])


def test_edges_represented_across_catalog_seeds(registry):
    """Spot-check representation across several catalog seeds per template."""
    from tests.conftest import catalog_entries

    for entry in catalog_entries():
        template = registry.get(entry["template_id"], entry.get("version"))
        for seed in entry["seeds"][:3]:
            task = generate_task(template, seed)
            assert set(task.edge_cases) == set(template.edge_cases)
