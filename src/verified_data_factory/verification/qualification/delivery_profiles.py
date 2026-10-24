"""Exact-version integration seams for the two approved follow-up contracts."""
from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import Any

PROFILE_MODULES = {
    ("sql.joins.requested_language_titles", 1): "language_titles_profile",
    ("sql.subqueries.pareto_shipping", 1): "pareto_shipping_profile",
    ("sql.retention.renewal_coverage", 1): "renewal_coverage_profile",
    ("sql.windows.queue_batches", 1): "queue_batches_profile",
}
PROFILE_IDS = frozenset(PROFILE_MODULES)
SCHEMAS = {
    ("sql.retention.renewal_coverage", 1): (
        ("episodes", (("episode_id", "INTEGER", False), ("member_id", "INTEGER", False), ("expires_at", "TIMESTAMP", False))),
        ("renewals", (("member_id", "INTEGER", False), ("begins_at", "TIMESTAMP", False), ("ends_at", "TIMESTAMP", False), ("status", "VARCHAR", False)))),
    ("sql.windows.queue_batches", 1): (
        ("submissions", (("submission_id", "INTEGER", False), ("queue", "VARCHAR", False), ("submitted_at", "TIMESTAMP", True))),),
    ("sql.joins.requested_language_titles", 1): (
        ("requests", (("request_id", "INTEGER", False), ("item_id", "INTEGER", True), ("language", "VARCHAR", True))),
        ("translations", (("item_id", "INTEGER", True), ("language", "VARCHAR", True), ("title", "VARCHAR", True)))),
    ("sql.subqueries.pareto_shipping", 1): (
        ("options", (("option_id", "INTEGER", False), ("lane", "VARCHAR", False),
                     ("cost_cents", "INTEGER", True), ("duration_minutes", "INTEGER", True))),),
}


def get_profile(contract: str, version: int) -> ModuleType | None:
    name = PROFILE_MODULES.get((contract, version))
    return import_module("." + name, __package__) if name else None


def schema_profile(definitions: Any) -> ModuleType | None:
    signature = tuple((table.name, tuple((c.name, c.type, c.nullable) for c in table.columns))
                      for table in sorted(definitions, key=lambda t: t.name))
    for pair, schema in SCHEMAS.items():
        if signature == schema:
            return get_profile(*pair)
    return None


def raw_key(contract: str, table: str, column: str) -> str:
    if contract in {"sql.joins.requested_language_titles", "sql.retention.renewal_coverage", "sql.windows.queue_batches"}:
        return f"raw:{table}.{column}"
    return {"option_id": "option_id_type", "lane": "lane_type", "cost_cents": "cost_type",
            "duration_minutes": "duration_type"}[column]


def public_specs(profile: ModuleType, reference: str) -> dict[str, Any]:
    specs: dict[str, Any] = profile.proofs(reference)
    for key in profile.STRUCTURAL_KEYS:
        specs[key]["wrong_sql"] = specs[key]["structural_sql"]
        specs[key]["outcome"] = "UNEXECUTED_RULE_SPEC"
    return specs


def candidate_specs(profile: ModuleType, sql: str, reference: str, public: dict[str, Any]) -> dict[str, Any] | None:
    # Profile AST derivation separates equivalent structural controls from kills.
    specs = {key: dict(value) for key, value in public.items()}
    for key in profile.STRUCTURAL_KEYS:
        specs[key].pop("wrong_sql", None)
    transforms = import_module(profile.__name__.removesuffix("_profile") + "_candidate_transforms")
    result: dict[str, Any] | None = transforms.candidate_proofs(sql, reference, specs)
    if result is not None:
        for key in profile.STRUCTURAL_KEYS:
            result[key]["wrong_sql"] = result[key]["structural_sql"]
    return result
