"""Criterion-specific full-catalog executed public-rule coverage measurement.

Missing detailed rule evidence is counted as uncovered, never as zero violations.
Malformed/stale/failed declared evidence refuses emission. This producer does not
invoke the frozen scorer or authorize a score from an incomplete input set.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from scripts.engineering_campaign import ROOT, safety, stamp
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.readiness import (
    authoritative_records,
    effective_evidence,
    receipt,
)
from verified_data_factory.verification.receipt_models import ArtifactRef
from verified_data_factory.verification.receipt_validation import (
    artifact,
    digest,
    required_sources,
    runtime_identity,
)

METRIC = "uncovered_or_violated_contract_rules"
PRODUCER = "scripts/engineering_rule_measurement.py"


def catalog_population() -> list[dict[str, Any]]:
    registry = load_builtin_registry()
    return [{"contract_id": name, "contract_version": registry.get(name).version}
            for name in sorted({template.template_id for template in registry.list()})]


def recompute(rows: Sequence[dict[str, Any]], expected: Sequence[dict[str, Any]]) -> int:
    if not expected or len(rows) != len(expected):
        raise ValueError("empty or partial rule measurement population")
    identities = [{"contract_id": row["contract_id"], "contract_version": row["contract_version"]} for row in rows]
    if identities != list(expected) or len({(row["contract_id"], row["contract_version"]) for row in rows}) != len(rows):
        raise ValueError("duplicated, stale or altered catalog population")
    missing = 0
    for row in rows:
        declared, covered = row["declared_rules"], row["covered_rules"]
        if not declared or len(declared) != len(set(declared)) or len(covered) != len(set(covered)):
            raise ValueError("empty or duplicate rule declarations")
        if not set(covered) <= set(declared):
            raise ValueError("coverage claims undeclared rules")
        if row["evidence_status"] not in {"REPLAYED_CURRENT", "ABSENT"}:
            raise ValueError("stale, partial or failed declared rule evidence")
        if row["evidence_status"] == "ABSENT" and covered:
            raise ValueError("absent evidence cannot claim coverage")
        missing += len(set(declared)-set(covered))
    return missing


def collect(root: Path) -> dict[str, Any]:
    expected = catalog_population()
    registry = load_builtin_registry()
    records = {(record["contract_id"], record["contract_version"]): record for record in authoritative_records(root)}
    sources = required_sources()
    sources[PRODUCER] = digest(root / PRODUCER)
    sources["tests/test_engineering_rule_measurement.py"] = digest(root / "tests/test_engineering_rule_measurement.py")
    for name in ("scratch/funnel_experiment/evidence/events.jsonl", "scratch/funnel_experiment/evidence/index.json",
                 "manifests/package-a-contract-quarantine.json"):
        sources[name] = digest(root / name)
    rows, sql_checks = [], 0

    def bind(value: Any) -> None:
        if isinstance(value, dict):
            if set(value) == {"path", "sha256"}:
                ref = ArtifactRef.model_validate(value)
                artifact(root, ref)
                sources[ref.path] = ref.sha256
            for name, checksum in value.get("source_hashes", {}).items():
                artifact(root, ArtifactRef(path=name, sha256=checksum))
                sources[name] = checksum
            for child in value.values():
                bind(child)
        elif isinstance(value, list):
            for child in value:
                bind(child)

    for identity in expected:
        pair = identity["contract_id"], identity["contract_version"]
        task = generate_task(registry.get(*pair), 94001)
        authority = public_behavior_map(task)
        declared = sorted(rule.rule_id for rule in authority.rules)
        record = records.get(pair)
        reference = record.get("evidence", {}).get("rules") if record else None
        if reference is None:
            rows.append({**identity, "declared_rules": declared, "covered_rules": [], "evidence_status": "ABSENT",
                         "reason": "no effective detailed rule receipt; all public obligations remain uncovered"})
            continue
        effective_evidence(root, record)
        data, reason = receipt(root, reference, *pair, "rules")
        if data is None:
            raise ValueError(f"declared rule receipt cannot be measured: {pair}: {reason}")
        covered = sorted(rule["rule_id"] for rule in data["details"]["rules"])
        bind(reference)
        bind(data)
        sql_checks += data["checks_run"]
        rows.append({**identity, "declared_rules": declared, "covered_rules": covered,
                     "evidence_status": "REPLAYED_CURRENT", "receipt": reference, "executed_receipt_checks": data["checks_run"]})
    value = recompute(rows, expected)
    for name, checksum in sources.items():
        artifact(root, ArtifactRef(path=name, sha256=checksum))
    return {"evidence_id": "criterion-contract-rules-"+stamp(), "producer": PRODUCER,
            "criterion": "correctness.contract_rules", "rubric_version": "engineering-1.0",
            "population": expected, "population_count": len(expected), "checks_run": len(rows)+sql_checks,
            "execution_failures": 0, "runtime": runtime_identity(), "source_hashes": sources,
            "metrics": {METRIC: value}, "rows": rows,
            "denominators": {"current_contracts": len(expected), "declared_public_rules": sum(len(row["declared_rules"]) for row in rows),
                             "replayed_rule_receipts": sum(row["evidence_status"] == "REPLAYED_CURRENT" for row in rows),
                             "contracts_without_rule_receipts": sum(row["evidence_status"] == "ABSENT" for row in rows),
                             "executed_receipt_checks": sql_checks},
            "interpretation": "executed proof-coverage reconciliation, not universal SQL correctness; missing obligations counted positively",
            "score_authorization": "NOT_READY_OTHER_CRITERIA_AND_FINAL_CERTIFICATION_REMAIN_DUE"}


def validate(root: Path, reference: dict[str, Any]) -> int:
    data = json.loads(artifact(root, ArtifactRef.model_validate(reference)).read_text())
    if data.get("producer") != PRODUCER or data.get("runtime") != runtime_identity() or data.get("execution_failures") != 0:
        raise ValueError("unsupported producer/runtime or failed measurement")
    expected = catalog_population()
    if data.get("population") != expected or data.get("population_count") != len(expected):
        raise ValueError("partial or stale full-catalog population")
    for name, checksum in data["source_hashes"].items():
        artifact(root, ArtifactRef(path=name, sha256=checksum))
    value = recompute(data["rows"], expected)
    if type(data["metrics"].get(METRIC)) is not int or data["metrics"][METRIC] != value:
        raise ValueError("altered metric differs from per-rule executed coverage")
    fresh = collect(root)
    if (data["rows"] != fresh["rows"] or data["source_hashes"] != fresh["source_hashes"]
            or data["metrics"] != fresh["metrics"] or data["denominators"] != fresh["denominators"]
            or data["checks_run"] != fresh["checks_run"]):
        raise ValueError("measurement differs from current executed authoritative reconciliation")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    safety()
    if args.output.exists():
        raise ValueError("measurement exists; use an unused output identity")
    result = collect(ROOT)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, sort_keys=True, indent=2)
    print(json.dumps({"criterion": result["criterion"], "metric": result["metrics"], "denominators": result["denominators"],
                      "score": "NOT_COMPUTABLE"}, indent=2))


if __name__ == "__main__":
    main()
