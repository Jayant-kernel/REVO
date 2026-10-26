"""Three frozen discrimination criteria over the complete current catalog."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.engineering_campaign import ROOT, safety, stamp
from scripts.engineering_rule_measurement import catalog_population
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

PRODUCER = "scripts/engineering_discrimination_measurement.py"
CATEGORIES = ("challenge", "fixture_diversity", "relations")
METRICS = {"challenge": "challenge_deficient_contracts", "fixture_diversity": "contracts_with_fewer_than_four_distinct_fixtures",
           "relations": "contracts_with_fewer_than_two_discriminating_relations"}


def recompute(rows: list[dict[str, Any]], expected: list[dict[str, Any]], thresholds: dict[str, Any]) -> dict[str, int]:
    if not expected or len(rows) != len(expected):
        raise ValueError("empty or partial discrimination population")
    ids = [{"contract_id": row["contract_id"], "contract_version": row["contract_version"]} for row in rows]
    if ids != expected or len({(row["contract_id"], row["contract_version"]) for row in rows}) != len(rows):
        raise ValueError("duplicate, altered or stale contract population")
    values = dict.fromkeys(METRICS.values(), 0)
    for row in rows:
        if set(row["categories"]) != set(CATEGORIES):
            raise ValueError("missing category observation")
        for category, observation in row["categories"].items():
            if observation["status"] == "ABSENT":
                values[METRICS[category]] += 1
                continue
            if observation["status"] != "REPLAYED_CURRENT":
                raise ValueError("failed or stale declared category evidence")
            metrics = observation["metrics"]
            if category == "challenge":
                bad = (metrics["witnessed_wrong"] < thresholds["minimum_wrong_challenges_per_contract"]
                       or metrics["qualified_correct"] < thresholds["minimum_correct_alternatives_per_contract"]
                       or metrics["false_acceptances"] != 0 or metrics["false_rejections"] != 0)
            elif category == "fixture_diversity":
                bad = metrics["distinct_contents"] < thresholds["minimum_distinct_fixtures_including_original"]
            else:
                bad = metrics["discriminating"] < thresholds["minimum_discriminating_relations_per_contract"] or metrics["failed"] != 0
            values[METRICS[category]] += int(bad)
    return values


def collect(root: Path) -> dict[str, Any]:
    expected = catalog_population()
    thresholds = json.loads((root / "configs/package_a/engineering-rubric.json").read_text())["thresholds"]
    records = {(record["contract_id"], record["contract_version"]): record for record in authoritative_records(root)}
    sources = required_sources()
    for name in (PRODUCER, "scripts/engineering_rule_measurement.py", "tests/test_engineering_discrimination_measurement.py",
                 "scratch/funnel_experiment/evidence/events.jsonl", "scratch/funnel_experiment/evidence/index.json",
                 "manifests/package-a-contract-quarantine.json"):
        sources[name] = digest(root / name)

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

    rows, checks = [], 0
    for identity in expected:
        pair = identity["contract_id"], identity["contract_version"]
        record = records.get(pair)
        observations = {}
        if record:
            effective_evidence(root, record)
        for category in CATEGORIES:
            reference = record.get("evidence", {}).get(category) if record else None
            if reference is None:
                observations[category] = {"status": "ABSENT", "reason": "no effective detailed category receipt; deficiency counted positively"}
                continue
            data, reason = receipt(root, reference, *pair, category)
            if data is None:
                raise ValueError(f"declared category evidence cannot be measured: {pair}/{category}: {reason}")
            bind(reference)
            bind(data)
            checks += data["checks_run"]
            observations[category] = {"status": "REPLAYED_CURRENT", "metrics": data["metrics"], "receipt": reference,
                                      "executed_receipt_checks": data["checks_run"]}
        rows.append({**identity, "categories": observations})
    for name, checksum in sources.items():
        artifact(root, ArtifactRef(path=name, sha256=checksum))
    return {"evidence_id": "criteria-discrimination-"+stamp(), "producer": PRODUCER, "rubric_version": "engineering-1.0",
            "population": expected, "population_count": len(expected), "checks_run": len(rows)*3+checks, "execution_failures": 0,
            "runtime": runtime_identity(), "source_hashes": sources, "rows": rows,
            "metrics": recompute(rows, expected, thresholds), "denominators": {"contracts": len(expected), "required_category_observations": len(expected)*3,
              "replayed_category_receipts": sum(observation["status"] == "REPLAYED_CURRENT" for row in rows for observation in row["categories"].values()),
              "executed_receipt_checks": checks},
            "interpretation": "missing categories remain measured deficiencies; not curated challenge accuracy or score authorization"}


def validate(root: Path, reference: dict[str, Any]) -> dict[str, int]:
    data = json.loads(artifact(root, ArtifactRef.model_validate(reference)).read_text())
    if data.get("producer") != PRODUCER or data.get("runtime") != runtime_identity() or data.get("execution_failures") != 0:
        raise ValueError("unsupported/stale/failed discrimination producer")
    if data.get("population") != catalog_population():
        raise ValueError("partial or stale full catalog")
    for name, checksum in data["source_hashes"].items():
        artifact(root, ArtifactRef(path=name, sha256=checksum))
    fresh = collect(root)
    for key in ("population_count", "checks_run", "source_hashes", "rows", "metrics", "denominators"):
        if data.get(key) != fresh[key]:
            raise ValueError("altered discrimination measurement differs from executed authority")
    return fresh["metrics"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    safety()
    if args.output.exists():
        raise ValueError("preserve existing metric; use unused identity")
    report = collect(ROOT)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, sort_keys=True, indent=2)
    print(json.dumps({"metrics": report["metrics"], "denominators": report["denominators"], "score": "NOT_COMPUTABLE"}, indent=2))


if __name__ == "__main__":
    main()
