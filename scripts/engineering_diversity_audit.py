"""Engineering isolation screens and actionable blocked-contract inventory."""
import argparse
import inspect
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engineering_campaign import OUT, ROOT, safety, stamp, write_new
from engineering_score import digest
from phase3_diagnostic import _reference_sql

from verified_data_factory.products.errors import ProductConfigError
from verified_data_factory.products.isolation import (
    schema_role_fingerprint,
    sql_structure_fingerprint,
)
from verified_data_factory.task_engine import load_builtin_registry
from verified_data_factory.verification.oracle_registry import get_oracle


def main() -> None:
    safety()
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default="")
    args = parser.parse_args()
    if args.revision and (not args.revision.startswith("r") or not args.revision[1:].isdigit()):
        raise ValueError("revision must be r followed by digits")
    refs = _reference_sql()
    latest = {}
    for template in load_builtin_registry().list():
        if template.template_id not in latest or latest[template.template_id].version < template.version:
            latest[template.template_id] = template
    records = []
    groups = defaultdict(list)
    behavioral = defaultdict(list)
    for contract, template in sorted(latest.items()):
        oracle = get_oracle(contract, template.version)
        role = schema_role_fingerprint([t.model_dump() for t in template.schema_definition])
        try:
            structure = sql_structure_fingerprint(refs[contract])
        except (ProductConfigError, KeyError):
            structure = "UNAVAILABLE"
        generic = oracle.fn.__name__ == "expansion_total"
        qualified = contract in {"sql.funnel.saas_activation_payment", "sql.aggregation.manufacturing_line_scrap"}
        path = "QUALIFIED_PROFILE_REFRESH_REQUIRED" if qualified else "SEMANTICS_SPECIFICATION_OR_FORWARD_IMPLEMENTATION" if generic else "NAMED_ORACLE_EVIDENCE_CANDIDATE"
        signature = None
        if generic:
            probes = [{"probe": [{"group_key": "probe", "status": status, "occurred_at": f"{year}-01-01", "amount": amount}]}
                      for status, year, amount in (("eligible", 2025, 7), ("ineligible", 2025, 7), ("eligible", 2024, 7), ("eligible", 2025, 0))]
            signature = [oracle.fn(template.requirements, p).rows for p in probes]
            behavioral[json.dumps(signature, sort_keys=True)].append(contract)
        groups[role].append(contract)
        records.append({"contract_id": contract, "version": template.version, "family": template.family,
                        "schema_role_hash": role, "reference_structure_hash": structure,
                        "qualification_path": path, "oracle": oracle.fn.__name__,
                        "rules_to_prove": sorted(template.requirements), "shared_probe_behavior": signature,
                        "instruction": template.instruction_template,
                        "oracle_source_available": bool(inspect.getsource(oracle.fn)),
                        "claim": "candidate plan, not qualification or independence proof"})
    suffix = "-" + args.revision if args.revision else ""
    write_new(OUT / f"phase9-diversity-and-blocked-plan{suffix}.json", {
        "created_at": stamp(), "contracts": records,
        "schema_screening_clusters": [v for v in groups.values() if len(v) > 1],
        "shared_probe_behavior_clusters": [v for v in behavioral.values() if len(v) > 1],
        "behavioral_scope": "Generic ledgers compared on four actual shared probes; named contracts with incompatible schemas remain UNMEASURED, not asserted unique",
        "structural_scope": "DuckDB parser AST with identifiers/literals abstracted; conservative isolation, not semantic-equivalence proof",
        "source_hashes": {p: digest(ROOT / p) for p in ("scripts/engineering_diversity_audit.py",
            "src/verified_data_factory/products/isolation.py", "src/verified_data_factory/verification/oracle_registry.py")}})
    print(json.dumps({"contracts": len(records), "generic_semantic_plans": sum(r["qualification_path"] == "SEMANTICS_SPECIFICATION_OR_FORWARD_IMPLEMENTATION" for r in records),
                      "named_evidence_candidates": sum(r["qualification_path"] == "NAMED_ORACLE_EVIDENCE_CANDIDATE" for r in records)}))


if __name__ == "__main__":
    main()
