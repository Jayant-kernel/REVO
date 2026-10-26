"""Actual shared-ledger probes; incompatible public schemas are not compared."""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engineering_campaign import OUT, safety, stamp, write_new

from verified_data_factory.task_engine import load_builtin_registry
from verified_data_factory.verification.oracle_registry import get_oracle


def main() -> None:
    safety()
    latest = {}
    for template in load_builtin_registry().list():
        if template.template_id not in latest or latest[template.template_id].version < template.version:
            latest[template.template_id] = template
    sequences = [[], ["eligible"], ["signup"], ["signup", "trial", "activation", "payment"],
                 ["accepted", "sorted", "dispatched", "delivered"],
                 ["signup", "activation", "payment"], ["eligible", "ineligible", "eligible"],
                 ["signup", "trial", "activation", "payment", "payment"]]
    records = []
    groups = defaultdict(list)
    for contract, template in sorted(latest.items()):
        schema = template.schema_definition
        required = {"record_id", "entity_id", "group_key", "occurred_at", "status", "amount", "sequence"}
        if len(schema) != 1 or {c.name for c in schema[0].columns} != required:
            records.append({"contract": contract, "version": template.version, "status": "NOT_APPLICABLE_SHARED_LEDGER",
                            "reason": "public schema is not the shared ledger domain; no invented cross-schema adapter or uniqueness claim"})
            continue
        signature = []
        for statuses in sequences:
            rows = [{"record_id": i, "entity_id": 1, "group_key": "probe", "occurred_at": "2025-01-01 00:00:00",
                     "sequence": i, "status": status, "amount": i * 7} for i, status in enumerate(statuses, 1)]
            result = get_oracle(contract, template.version).fn(template.requirements, {schema[0].name: rows})
            signature.append({"columns": result.columns, "rows": result.rows})
        groups[json.dumps(signature, sort_keys=True)].append(contract)
        records.append({"contract": contract, "version": template.version, "status": "EXECUTED_SHARED_PROBES", "signature": signature})
    write_new(OUT / "phase9-shared-probes.json", {"created_at": stamp(), "records": records,
            "probe_sequences": sequences, "behavioral_duplicate_clusters_on_these_probes": [v for v in groups.values() if len(v) > 1],
            "limitation": "finite shared-probe agreement is not universal query equivalence"})
    print(json.dumps({"compatible_contracts": sum(r["status"] == "EXECUTED_SHARED_PROBES" for r in records),
                      "clusters": [v for v in groups.values() if len(v) > 1]}, indent=2))


if __name__ == "__main__":
    main()
