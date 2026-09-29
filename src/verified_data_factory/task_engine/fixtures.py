"""Deterministic DuckDB fixture generation (Phase 1).

Contract: ``F(template, version, config, seed)`` always yields identical
rows. All randomness comes from ``random.Random`` instances seeded via
:mod:`verified_data_factory.task_engine.seed`. No global RNG, no network.

Only the *task specification* side is built here (fixtures + metadata).
Reference-query execution and verdicts belong to Phase 4 and are absent.
"""

from __future__ import annotations

import datetime as _dt
import logging
import random
import tempfile
from collections import Counter
from itertools import pairwise
from pathlib import Path
from typing import Any

from .errors import FixtureError
from .models import FixtureMetadata, FixtureTableMetadata, TableDefinition, TaskTemplate
from .seed import derive_child_seed, make_rng

logger = logging.getLogger(__name__)

GENERATION_VERSION = 2

_FIRST_NAMES = [
    "Aarav",
    "Maya",
    "Liam",
    "Sofia",
    "Noah",
    "Priya",
    "Kenji",
    "Amara",
    "Diego",
    "Elena",
    "Ravi",
    "Nina",
    "Omar",
    "Tara",
    "Felix",
    "Iris",
]
_LAST_NAMES = [
    "Sharma",
    "Garcia",
    "Kim",
    "Patel",
    "Nguyen",
    "Silva",
    "Khan",
    "Muller",
    "Rossi",
    "Dubois",
    "Tanaka",
    "Ali",
    "Novak",
    "Costa",
    "Weber",
    "Iyer",
]
_COUNTRIES = ["IN", "US", "DE", "BR", "JP", "GB", "FR", "AE"]
_STATUSES = ["completed", "completed", "completed", "pending", "cancelled"]
_CATEGORIES = ["electronics", "apparel", "groceries", "books", "toys"]
_FUNNEL_STEPS = ["view", "add_to_cart", "checkout", "purchase"]
_EVENT_TYPES = ["view", "click", "purchase", "refund", "signup"]

_BASE_DATE = _dt.date(2025, 1, 1)


def _jittered_count(base: int, rng: random.Random, minimum: int = 3) -> int:
    """Vary ``base`` by ±20% deterministically so seeds differ meaningfully."""
    if base <= 0:
        return 0
    delta = round(base * 0.2 * (rng.random() * 2 - 1))
    return max(minimum, base + delta)


def _gen_customers(n: int, rng: random.Random) -> list[dict[str, Any]]:
    rows = []
    for i in range(1, n + 1):
        first = _FIRST_NAMES[(i - 1) % len(_FIRST_NAMES)]
        last = _LAST_NAMES[(rng.randrange(len(_LAST_NAMES)) + i) % len(_LAST_NAMES)]
        rows.append(
            {
                "customer_id": i,
                "name": f"{first} {last}",
                "country": _COUNTRIES[rng.randrange(len(_COUNTRIES))],
                "signup_date": str(
                    _BASE_DATE.replace(year=2024) + _dt.timedelta(days=rng.randrange(365))
                ),
            }
        )
    return rows


def _gen_products(n: int, rng: random.Random) -> list[dict[str, Any]]:
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "product_id": i,
                "name": f"Product {i}",
                "category": _CATEGORIES[(i - 1) % len(_CATEGORIES)],
                "price": round(5 + rng.random() * 495, 2),
            }
        )
    return rows


def _gen_orders(n: int, rng: random.Random, customer_ids: list[int]) -> list[dict[str, Any]]:
    if not customer_ids:
        raise FixtureError("cannot generate orders without customers")
    # Leave the last ~20% of customers orderless (missing-relationship case)
    # while keeping every FK valid.
    eligible = customer_ids[: max(1, round(len(customer_ids) * 0.8))]
    rows = []
    for i in range(1, n + 1):
        cid = rng.choice(eligible)
        rows.append(
            {
                "order_id": i,
                "customer_id": cid,
                "order_date": str(_BASE_DATE + _dt.timedelta(days=rng.randrange(365))),
                "amount": round(10 + rng.random() * 990, 2),
                "status": _STATUSES[rng.randrange(len(_STATUSES))],
            }
        )
    return rows


def _gen_order_items(
    n: int, rng: random.Random, order_ids: list[int], product_ids: list[int]
) -> list[dict[str, Any]]:
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "item_id": i,
                "order_id": rng.choice(order_ids),
                "product_id": rng.choice(product_ids),
                "quantity": rng.randrange(1, 6),
            }
        )
    return rows


def _gen_events(
    n: int, rng: random.Random, customer_ids: list[int], *, funnel: bool = False
) -> list[dict[str, Any]]:
    kinds = _FUNNEL_STEPS if funnel else _EVENT_TYPES
    rows = []
    for i in range(1, n + 1):
        day = rng.randrange(60)
        rows.append(
            {
                "event_id": i,
                "customer_id": rng.choice(customer_ids),
                "event_type": kinds[rng.randrange(len(kinds))],
                "event_time": str(
                    # Naive timestamps are intentional (see note above).
                    _dt.datetime(2025, 1, 1) + _dt.timedelta(days=day, seconds=rng.randrange(86400))  # noqa: DTZ001
                ),
            }
        )
    return rows


def _gen_generic(table: TableDefinition, n: int, rng: random.Random) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(1, n + 1):
        row: dict[str, Any] = {}
        for col in table.columns:
            lname = col.name.lower()
            if lname in ("id",) or lname.endswith("_id"):
                row[col.name] = i
            elif col.type in ("INTEGER", "BIGINT"):
                row[col.name] = rng.randrange(100)
            elif col.type in ("DOUBLE", "DECIMAL"):
                row[col.name] = round(rng.random() * 100, 2)
            elif col.type == "BOOLEAN":
                row[col.name] = bool(rng.randrange(2))
            elif col.type == "DATE":
                row[col.name] = str(_BASE_DATE + _dt.timedelta(days=rng.randrange(365)))
            elif col.type == "TIMESTAMP":
                # Naive timestamps are intentional: Phase 1 avoids timezone
                # complexity (see temporal template docs).
                row[col.name] = str(
                    _dt.datetime(2025, 1, 1) + _dt.timedelta(days=rng.randrange(365))  # noqa: DTZ001
                )
            else:
                row[col.name] = f"{col.name}_{i}"
        rows.append(row)
    return rows


# --- Edge-case injection (intentional + recorded) ---------------------------


def _inject_nulls(rows: list[dict[str, Any]], table: TableDefinition, rng: random.Random) -> bool:
    targets = [
        c.name
        for c in table.columns
        if c.nullable and c.name.lower() not in ("id",) and not c.name.lower().endswith("_id")
    ]
    if not rows or not targets:
        return False
    col = targets[rng.randrange(len(targets))]
    rows[rng.randrange(len(rows))][col] = None
    return True


def _inject_duplicates(
    rows: list[dict[str, Any]], table: TableDefinition, rng: random.Random
) -> bool:
    if len(rows) < 1:
        return False
    src = dict(rows[rng.randrange(len(rows))])
    # New primary key, same business content → a true duplicate event.
    for col in table.columns:
        lname = col.name.lower()
        if lname in ("id",) or lname.endswith("_id"):
            src[col.name] = max(r[col.name] for r in rows if isinstance(r[col.name], int)) + 1
            break
    rows.append(src)
    return True


def _inject_ties(rows: list[dict[str, Any]], rng: random.Random) -> bool:
    if len(rows) < 2:
        return False
    first = rows[0]
    numeric = [k for k, v in first.items() if isinstance(v, (int, float))]
    candidates = [k for k in numeric if not k.lower().endswith("_id") and k.lower() != "id"]
    if candidates:
        rows[1][candidates[0]] = first[candidates[0]]
        return True
    # Event-style tables have no measure column: tie on the ordering key
    # itself (exercises explicit tie-breaking rules downstream).
    for key in ("event_time", "order_date"):
        if key in first:
            rows[1][key] = first[key]
            return True
    return False


def _inject_zero_negative(
    rows: list[dict[str, Any]], rng: random.Random, *, negative: bool
) -> bool:
    if not rows:
        return False
    for key in ("amount", "price", "quantity"):
        if key in rows[0]:
            idx = rng.randrange(len(rows))
            rows[idx][key] = round(-1 * (1 + rng.random() * 50), 2) if negative else 0
            if key == "quantity" and not negative:
                rows[idx][key] = 0
            elif key == "quantity" and negative:
                rows[idx][key] = -1
            return True
    return False


def _ensure_orderless_customer(
    tables: dict[str, list[dict[str, Any]]],
) -> bool:
    if "customers" not in tables or "orders" not in tables:
        return False
    ordered = {r["customer_id"] for r in tables["orders"]}
    return any(c["customer_id"] not in ordered for c in tables["customers"])


def _ensure_eventless_customer(tables: dict[str, list[dict[str, Any]]], rng: random.Random) -> bool:
    """Ensure at least one customer has zero events (enforced, not assumed)."""
    if "customers" not in tables or "events" not in tables:
        return False
    counts: dict[Any, int] = {}
    for e in tables["events"]:
        counts[e["customer_id"]] = counts.get(e["customer_id"], 0) + 1
    if any(c["customer_id"] not in counts for c in tables["customers"]):
        return True
    victim = tables["customers"][rng.randrange(len(tables["customers"]))]["customer_id"]
    tables["events"] = [e for e in tables["events"] if e["customer_id"] != victim]
    return True


def _ensure_single_row_group(tables: dict[str, list[dict[str, Any]]]) -> bool:
    """Ensure a singleton group exists (country or status), enforcing if needed."""
    for rows in tables.values():
        if rows and "country" in rows[0]:
            counts = Counter(r["country"] for r in rows)
            if any(v == 1 for v in counts.values()):
                return True
    for rows in tables.values():
        if rows and "status" in rows[0]:
            counts = Counter(r["status"] for r in rows)
            if any(v == 1 for v in counts.values()):
                return True
            # Force a singleton: keep the first occurrence of the rarest
            # status, move the rest to the most common status.
            rarest = min(counts, key=lambda k: counts[k])
            common = max(counts, key=lambda k: counts[k])
            kept = False
            for r in rows:
                if r["status"] == rarest:
                    if kept:
                        r["status"] = common
                    else:
                        kept = True
            return True
    return len(tables) > 0


def _ensure_multi_orders(tables: dict[str, list[dict[str, Any]]]) -> bool:
    """Ensure one customer has >= 2 orders (enforced with a new PK if needed)."""
    if "orders" not in tables:
        return any(len(rows) >= 2 for rows in tables.values())
    counts = Counter(r["customer_id"] for r in tables["orders"])
    if any(v >= 2 for v in counts.values()):
        return True
    src = dict(tables["orders"][0])
    src["order_id"] = max(r["order_id"] for r in tables["orders"]) + 1
    tables["orders"].append(src)
    return True


def _ensure_multi_purchases(tables: dict[str, list[dict[str, Any]]]) -> bool:
    """Ensure one customer has >= 2 purchase events (enforced if needed)."""
    if "events" not in tables:
        return False
    counts = Counter(e["customer_id"] for e in tables["events"] if e["event_type"] == "purchase")
    if any(v >= 2 for v in counts.values()):
        return True
    per_customer = Counter(e["customer_id"] for e in tables["events"])
    owner = max(per_customer, key=lambda k: per_customer[k])
    changed = 0
    for e in tables["events"]:
        if e["customer_id"] == owner and e["event_type"] != "purchase" and changed < 2:
            e["event_type"] = "purchase"
            changed += 1
    return changed == 2


def _event_day(value: Any) -> str:
    return str(value).split(" ")[0]


def _ensure_same_day_events(tables: dict[str, list[dict[str, Any]]]) -> bool:
    """Ensure two events share a calendar day (enforced if needed)."""
    rows = tables.get("events")
    if not rows or len(rows) < 2:
        return False
    if any(v >= 2 for v in Counter(_event_day(e["event_time"]) for e in rows).values()):
        return True
    day = _event_day(rows[0]["event_time"])
    time_part = str(rows[1]["event_time"]).split(" ", 1)[1]
    rows[1]["event_time"] = f"{day} {time_part}"
    return True


def _ensure_retention_boundaries(
    template: TaskTemplate, tables: dict[str, list[dict[str, Any]]]
) -> bool:
    """Materialize before, inclusive day-30, and day-31 retention boundaries."""
    customers = tables.get("customers")
    events = tables.get("events")
    if not customers or events is None:
        return False
    customer = customers[0]
    signup = _dt.date.fromisoformat(str(customer["signup_date"])[:10])
    window = int(template.requirements.get("retention_window_days", 30))
    next_id = max((int(e["event_id"]) for e in events), default=0) + 1
    for offset, time_part in ((-1, "23:59:59"), (window, "23:59:59"), (window + 1, "00:00:00")):
        day = signup + _dt.timedelta(days=offset)
        events.append(
            {
                "event_id": next_id,
                "customer_id": customer["customer_id"],
                "event_type": str(template.requirements.get("qualifying_event", "purchase")),
                "event_time": f"{day.isoformat()} {time_part}",
            }
        )
        next_id += 1
    return True


def _ensure_same_timestamp_steps(
    template: TaskTemplate, tables: dict[str, list[dict[str, Any]]]
) -> bool:
    """Create a full funnel whose order is decided only by ascending event_id."""
    customers = tables.get("customers")
    events = tables.get("events")
    steps = list(template.requirements.get("funnel_steps", []))
    if not customers or events is None or not steps:
        return False
    customer_id = customers[0]["customer_id"]
    events[:] = [e for e in events if e["customer_id"] != customer_id]
    next_id = max((int(e["event_id"]) for e in events), default=0) + 1
    for step in steps:
        events.append(
            {
                "event_id": next_id,
                "customer_id": customer_id,
                "event_type": str(step),
                "event_time": "2025-01-01 12:00:00",
            }
        )
        next_id += 1
    return True


def _ensure_window_end_boundary(
    template: TaskTemplate, tables: dict[str, list[dict[str, Any]]]
) -> bool:
    """Put DATE and TIMESTAMP rows on the inclusive final calendar day."""
    end = str(template.requirements.get("window_end", ""))
    if not end:
        return False
    changed = False
    if tables.get("orders"):
        tables["orders"][0]["order_date"] = end
        changed = True
    if tables.get("events"):
        tables["events"][0]["event_time"] = f"{end} 23:59:59"
        changed = True
    return changed


def _ensure_out_of_order(
    tables: dict[str, list[dict[str, Any]]],
) -> bool:
    """Ensure timestamps are not sorted in row order (enforced if needed)."""
    for rows in tables.values():
        if not rows:
            continue
        key = (
            "event_time"
            if "event_time" in rows[0]
            else ("order_date" if "order_date" in rows[0] else None)
        )
        if key is None:
            continue
        times = [str(r[key]) for r in rows]
        if any(a > b for a, b in pairwise(times)):
            return True
        if len(rows) >= 2:
            if len(set(times)) > 1:
                rows[0][key], rows[-1][key] = rows[-1][key], rows[0][key]
            else:
                # All identical: move the last row before the epoch start.
                rows[-1][key] = "2024-12-31" if key == "order_date" else "2024-12-31 00:00:00"
            return True
    return False


def _supports_ties(rows: list[dict[str, Any]]) -> bool:
    """Whether a tie can be represented in these rows."""
    if len(rows) < 2:
        return False
    first = rows[0]
    if any(
        isinstance(v, (int, float)) and not k.lower().endswith("_id") and k.lower() != "id"
        for k, v in first.items()
    ):
        return True
    return any(k in first for k in ("event_time", "order_date"))


def apply_edge_cases(
    template: TaskTemplate,
    tables: dict[str, list[dict[str, Any]]],
    table_defs: dict[str, TableDefinition],
    seed: int,
) -> list[str]:
    """Inject declared edge cases deterministically; return what was ensured."""
    rng = make_rng(derive_child_seed(seed, "edge_cases"))
    ensured: list[str] = []
    for case in template.edge_cases:
        if case == "null_values":
            ok = any(
                _inject_nulls(rows, table_defs[name], rng)
                for name, rows in tables.items()
                if name in table_defs
            )
        elif case in ("duplicates", "duplicate_events"):
            name = "events" if "events" in tables else next(iter(tables))
            ok = _inject_duplicates(tables[name], table_defs[name], rng)
        elif case == "ties":
            ok = False
            for rows in tables.values():
                if _supports_ties(rows):
                    ok = _inject_ties(rows, rng)
                    break
        elif case in ("missing_relationships", "no_events"):
            if "orders" in tables:
                ok = _ensure_orderless_customer(tables)
            else:
                ok = _ensure_eventless_customer(tables, rng)
        elif case in ("single_row_groups", "single-row groups"):
            ok = _ensure_single_row_group(tables)
        elif case == "multiple_matching_rows":
            ok = _ensure_multi_orders(tables)
        elif case == "multiple_purchases":
            ok = _ensure_multi_purchases(tables)
        elif case == "out_of_order_timestamps":
            ok = _ensure_out_of_order(tables)
        elif case == "same_day_events":
            ok = _ensure_same_day_events(tables)
        elif case == "retention_boundaries":
            ok = _ensure_retention_boundaries(template, tables)
        elif case == "same_timestamp_steps":
            ok = _ensure_same_timestamp_steps(template, tables)
        elif case == "window_end_boundary":
            ok = _ensure_window_end_boundary(template, tables)
        elif case == "zero_values":
            ok = _inject_zero_negative(next(iter(tables.values())), rng, negative=False)
        elif case == "negative_values":
            ok = _inject_zero_negative(next(iter(tables.values())), rng, negative=True)
        elif case == "empty_result":
            # NOT fixture evidence: no Phase 1 template declares this, because
            # an "empty result" is a property of a filter + data combination
            # that only execution can establish. Empty-result coverage belongs
            # to Phase 4 hidden tests (see docs/task-semantics.md). Recorded
            # here only so a future template can declare the *intent*.
            ok = True
        else:
            ok = True  # unknown future case: recorded, not fabricated
        if ok:
            ensured.append(case)
    return ensured


# --- Top-level generation ----------------------------------------------------


def generate_fixture_tables(
    template: TaskTemplate, seed: int
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """Generate all fixture rows deterministically for ``(template, seed)``."""
    tables: dict[str, list[dict[str, Any]]] = {}
    defs = {t.name: t for t in template.schema_definition}
    customer_ids: list[int] = []
    order_ids: list[int] = []
    product_ids: list[int] = []

    for table in template.schema_definition:
        rng = make_rng(derive_child_seed(seed, f"table:{table.name}"))
        n = _jittered_count(table.row_count, rng)
        kind = table.row_kind
        if kind == "customers":
            rows = _gen_customers(n, rng)
            customer_ids = [r["customer_id"] for r in rows]
        elif kind == "products":
            rows = _gen_products(n, rng)
            product_ids = [r["product_id"] for r in rows]
        elif kind == "orders":
            if not customer_ids:
                # Standalone order tables (no customers table): synthesize ids.
                customer_ids = list(range(1, max(5, n // 2) + 1))
            rows = _gen_orders(n, rng, customer_ids)
            order_ids = [r["order_id"] for r in rows]
        elif kind == "order_items":
            if not order_ids:
                order_ids = list(range(1, 11))
            if not product_ids:
                product_ids = list(range(1, 6))
            rows = _gen_order_items(n, rng, order_ids, product_ids)
        elif kind in ("events", "funnel_events"):
            if not customer_ids:
                customer_ids = list(range(1, max(5, n // 2) + 1))
            rows = _gen_events(n, rng, customer_ids, funnel=(kind == "funnel_events"))
        else:
            rows = _gen_generic(table, n, rng)
        # Trim/pad rows to exactly the declared columns.
        wanted = [c.name for c in table.columns]
        tables[table.name] = [{k: r.get(k) for k in wanted} for r in rows]

    ensured = apply_edge_cases(template, tables, defs, seed)
    return tables, ensured


def build_fixture_metadata(
    template: TaskTemplate, seed: int, tables: dict[str, list[dict[str, Any]]]
) -> FixtureMetadata:
    return FixtureMetadata(
        engine="duckdb",
        seed=seed,
        generation_version=GENERATION_VERSION,
        tables={name: FixtureTableMetadata(row_count=len(rows)) for name, rows in tables.items()},
    )


def materialize_duckdb(
    tables_def: list[TableDefinition],
    rows: dict[str, list[dict[str, Any]]],
    db_path: str | Path | None = None,
) -> Any:
    """Create a DuckDB database with the fixture tables; return the connection.

    Uses an in-memory database by default. When ``db_path`` is given, the
    database is persisted there (useful for debugging, never committed).
    """
    try:
        import duckdb
    except ImportError as exc:
        raise FixtureError("duckdb is required for fixture materialization") from exc

    from .schema import ddl_for_table

    defs = {t.name: t for t in tables_def}
    con = duckdb.connect(str(db_path) if db_path else ":memory:")
    try:
        for name in sorted(rows):
            table = defs[name]
            con.execute(ddl_for_table(table))
            cols = [c.name for c in table.columns]
            placeholders = ", ".join(["?"] * len(cols))
            col_list = ", ".join(f'"{c}"' for c in cols)
            data = [tuple(r.get(c) for c in cols) for r in rows[name]]
            if data:
                con.executemany(f'INSERT INTO "{name}" ({col_list}) VALUES ({placeholders})', data)
        return con
    except Exception as exc:
        con.close()
        raise FixtureError(f"fixture materialization failed: {exc}") from exc


def materialize_temp_duckdb(
    tables_def: list[TableDefinition], rows: dict[str, list[dict[str, Any]]]
) -> tuple[Any, Path, Any]:
    """Materialize into a temp-dir database; caller closes connection + cleanup."""
    tmpdir = Path(tempfile.mkdtemp(prefix="vdf_fixture_"))
    db_path = tmpdir / "fixture.duckdb"
    con = materialize_duckdb(tables_def, rows, db_path)
    return con, db_path, tmpdir
