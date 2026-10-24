"""Conservative rename-resistant grouping; fingerprints are not equivalence proofs."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import duckdb

from verified_data_factory.local_lock import exclusive_lock

from .errors import ProductConfigError


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def schema_role_fingerprint(schema: list[dict[str, Any]]) -> str:
    if not schema or any(not table.get("columns") for table in schema):
        raise ProductConfigError("schema role metadata missing")
    shapes = [sorted((column["type"].upper(), column.get("nullable", True)) for column in table["columns"]) for table in schema]
    roles: list[Any] = []
    for table in schema:
        for column in table["columns"]:
            declared = {key: column[key] for key in ("key_role", "primary_key", "unique") if key in column}
            if "references" in column:
                # Names are deliberately abstracted; retain the declared relationship
                # role and arity. This conservative screen is not graph equivalence.
                reference = column["references"]
                declared["references"] = len(reference.get("columns", [])) if isinstance(reference, dict) else "declared"
            if declared:
                roles.append((column["type"].upper(), column.get("nullable", True), declared))
        if table.get("foreign_keys"):
            roles.append(("FOREIGN_KEYS", len(table["foreign_keys"])))
        if table.get("primary_key"):
            roles.append(("PRIMARY_KEY", len(table["primary_key"])))
    if roles:
        return digest({"shapes": sorted(shapes), "declared_roles": sorted(roles, key=lambda role: json.dumps(role, sort_keys=True))})
    return digest(sorted(shapes))


def sql_structure_fingerprint(sql: str) -> str:
    connection = duckdb.connect()
    try:
        row = connection.execute("SELECT json_serialize_sql(?)", [sql]).fetchone()
        if row is None:
            raise ProductConfigError("SQL AST unavailable")
        ast = json.loads(row[0])
    finally:
        connection.close()
    if ast.get("error"):
        raise ProductConfigError("SQL AST unavailable; structural isolation cannot be established")
    def normalize(value: Any) -> Any:
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if not isinstance(value, dict):
            return value
        result: dict[str, Any] = {}
        for key, child in value.items():
            if key in {"query_location", "query_length", "start", "end", "location"}:
                continue
            if key in {"table_name", "schema_name", "catalog_name", "alias", "cte_name", "key"}:
                result[key] = "IDENTIFIER"
            elif key == "column_names":
                result[key] = ["IDENTIFIER"] * len(child)
            elif value.get("class") == "CONSTANT" and key == "value":
                result[key] = "LITERAL"
            else:
                result[key] = normalize(child)
        return result
    return digest(normalize(ast))


def isolation_keys(golden: Any) -> set[str]:
    task = golden.task
    if not task.get("template_id") or not task.get("template_version"):
        raise ProductConfigError("template lineage metadata missing")
    return {"template:" + task["template_id"], "schema:" + schema_role_fingerprint(golden.schema_),
            "structure:" + sql_structure_fingerprint(golden.candidate_solution)}


def connected_groups(goldens: list[Any]) -> dict[str, str]:
    parent = {g.candidate_id: g.candidate_id for g in goldens}
    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value
    first: dict[str, str] = {}
    for golden in sorted(goldens, key=lambda g: g.candidate_id):
        for key in sorted(isolation_keys(golden)):
            if key in first:
                a, b = find(golden.candidate_id), find(first[key])
                parent[max(a, b)] = min(a, b)
            else:
                first[key] = golden.candidate_id
    members: dict[str, list[str]] = {}
    for candidate in parent:
        members.setdefault(find(candidate), []).append(candidate)
    return {candidate: "engineering:" + digest(sorted(members[find(candidate)])) for candidate in parent}


def register_roles(path: Path, goldens: list[Any], role: str) -> None:
    if role not in {"TRAIN", "EVAL"}:
        raise ProductConfigError("unknown isolation role")
    with exclusive_lock(path.with_suffix(path.suffix + ".lock")):
        entries = json.loads(path.read_text()) if path.exists() else {}
        keys = {key for g in goldens for key in isolation_keys(g)}
        if any(key in entries and entries[key] != role for key in keys):
            raise ProductConfigError("schema/template/structure crosses training and evaluation products")
        updated = {**entries, **dict.fromkeys(keys, role)}
        temporary = path.with_suffix(path.suffix + "." + uuid4().hex + ".pending")
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(updated, handle, sort_keys=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
