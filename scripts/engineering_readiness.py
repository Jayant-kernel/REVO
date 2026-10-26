"""Generate the engineering manifest once, only from executable evidence."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engineering_campaign import OUT, ROOT, safety, stamp, write_new

from verified_data_factory.task_engine import load_builtin_registry
from verified_data_factory.verification.readiness import qualify, sha256


def main() -> None:
    safety()
    index_path = OUT / "phase6-contract-evidence.json"
    if index_path.exists():
        raise ValueError("readiness already generated; preserve evidence and explicit supersession")
    quarantine = json.loads((ROOT / "manifests/package-a-contract-quarantine.json").read_text())
    quarantine_by_key = {(q["contract_id"], q["contract_version"]): q for q in quarantine["quarantines"]}
    latest = {}
    for template in load_builtin_registry().list():
        if template.template_id not in latest or latest[template.template_id].version < template.version:
            latest[template.template_id] = template
    records = []
    for contract, template in sorted(latest.items()):
        record = {"contract_id": contract, "contract_version": template.version, "family": template.family,
                  "independence": "differential verification", "prerequisites": {"template_validates": True},
                  "evidence": {}, "quarantine": quarantine_by_key.get((contract, template.version))}
        # Existing aggregate receipts are useful history but not the required
        # per-contract complete/fresh category schema. Never fill absent fields.
        record.update(qualify(ROOT, record))
        records.append(record)
    write_new(index_path, {"version": "engineering-evidence-1.0", "generated_at": stamp(),
                           "producer": "scripts/engineering_readiness.py", "contracts": records,
                           "limitations": "Category producers must emit complete fresh receipts before admission; 0 eligible is permitted."})
    manifest_path = ROOT / "manifests/phase3-contract-readiness.json"
    old = manifest_path.read_bytes()
    archive = OUT / "phase6-superseded-readiness.json"
    with archive.open("xb") as handle:
        handle.write(old)
    payload = {"manifest_version": "engineering-3.0", "evidence_index": {
        "path": index_path.relative_to(ROOT).as_posix(), "sha256": sha256(index_path)},
        "contracts": [{"contract_id": r["contract_id"], "template_version": r["contract_version"],
                       "family": r["family"], "status": r["status"]} for r in records],
        "supersedes": {"path": archive.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(old).hexdigest()}}
    payload["manifest_hash"] = "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_new(OUT / "phase6-readiness-count.json", {"totals": dict(Counter(r["status"] for r in records)),
                                                  "contracts": len(records), "eligible": sum(r["eligible"] for r in records)})
    print(json.dumps({"contracts": len(records), "totals": dict(Counter(r["status"] for r in records))}))


if __name__ == "__main__":
    main()
