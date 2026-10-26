"""Reconcile the entire current catalog; never turn partial coverage into a score."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.engineering_campaign import ROOT, safety, stamp
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.readiness import authoritative_records, qualify
from verified_data_factory.verification.receipt_validation import (
    digest,
    required_sources,
    runtime_identity,
)


def population() -> list[tuple[str, int]]:
    registry = load_builtin_registry()
    return sorted((name, registry.get(name).version) for name in {t.template_id for t in registry.list()})


def audit(root: Path) -> dict[str, Any]:
    registry = load_builtin_registry()
    committed = {(r["contract_id"], r["contract_version"]): r for r in authoritative_records(root)}
    plan_path = root / "scratch/funnel_experiment/engineering/phase9-diversity-and-blocked-plan-r1.json"
    plans = {r["contract_id"]: r for r in json.loads(plan_path.read_text())["contracts"]}
    contracts = []
    for name, version in population():
        template = registry.get(name, version)
        task = generate_task(template, 94001)
        record = committed.get((name, version), {"contract_id": name, "contract_version": version,
            "independence": "differential verification", "prerequisites": {"template_validates": True}, "evidence": {}})
        result = qualify(root, record)
        authority = public_behavior_map(task)
        plan = plans.get(name, {})
        contracts.append({"contract_id": name, "contract_version": version, "family": template.family,
            "qualification": result, "required_semantic_rules": list(authority.semantic_rule_ids),
            "required_domain_rules": list(authority.domain_rule_ids), "granular_public_map": authority.granular,
            "required_structural_rules": list(authority.structural_rule_ids),
            "historical_plan_kind": plan.get("qualification_path"),
            "next_action": ("retain current complete evidence" if result["eligible"] else
                "resolve exact business/forward-schema intent, then execute complete qualification" if
                plan.get("qualification_path") == "SEMANTICS_SPECIFICATION_OR_FORWARD_IMPLEMENTATION" else
                "implement clause-specific public proofs and all seven executed categories; named oracle is not qualification"),
            "evidence": record["evidence"]})
    eligible = [c for c in contracts if c["qualification"]["eligible"]]
    sources = required_sources()
    for relative in ("scripts/engineering_program_audit.py", plan_path.relative_to(root).as_posix(),
                     "scratch/funnel_experiment/evidence/events.jsonl", "scratch/funnel_experiment/evidence/index.json",
                     "manifests/package-a-contract-quarantine.json"):
        sources[relative] = digest(root / relative)
    # These counts measure absence of complete qualification, not invented success
    # or generic test counts standing in for semantic behavior evidence.
    deficiencies = len(contracts) - len(eligible)
    return {"evidence_id": "full-catalog-audit-" + stamp(), "producer": "scripts/engineering_program_audit.py",
        "created_at": stamp(), "population": [{"contract_id": name, "contract_version": version} for name, version in population()],
        "population_count": len(contracts), "checks_run": len(contracts), "execution_failures": 0,
        "source_hashes": sources, "runtime": runtime_identity(), "contracts": contracts,
        "counts": dict(Counter(c["qualification"]["status"] for c in contracts)),
        "registered_families": dict(Counter(c["family"] for c in contracts)),
        "metrics": {"public_obligations_without_complete_current_qualification": sum(len(c["required_semantic_rules"]) + len(c["required_domain_rules"]) + len(c["required_structural_rules"])
                    for c in contracts if not c["qualification"]["eligible"]),
                    "contracts_without_complete_current_qualification": deficiencies},
        "metric_scope": "diagnostic reconciliation only; these are not substitutes for frozen criterion-specific metrics",
        "forward_dataset": {"status": "BLOCKED", "accepted_records": 0,
            "reason": "no new 80-record strict dataset acceptance artifact has been established",
            "qualified_families_available": sorted({c["family"] for c in eligible}),
            "required_records": 80, "required_per_family": 8, "required_distinct_instructions": 40,
            "coverage_constructs_edges_domains_duplicates": "NOT_MEASURED for a forward accepted dataset"},
        "score_status": "NOT_COMPUTABLE", "score_reasons": ["complete criterion-specific metric inputs not established",
            "final regression, final smoke and forward dataset acceptance have not been established"],
        "learning_value": "NOT_MEASURED", "authorship": "differential verification; independent authorship unproven"}


def main() -> None:
    safety()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(ROOT)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps({"population": report["population_count"], "counts": report["counts"], "score": report["score_status"]}))


if __name__ == "__main__":
    main()
