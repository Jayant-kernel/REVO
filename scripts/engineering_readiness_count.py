"""Independent artifact counting; never trusts the matrix's status labels."""
import json
from pathlib import Path
from typing import Any

from verified_data_factory.verification.readiness import qualify


def count(root: Path, path: Path) -> dict[str, Any]:
    index = json.loads(path.read_text())
    statuses = {"FULLY_VERIFIED": 0, "QUARANTINED": 0, "NOT_READY": 0}
    findings: list[dict[str, Any]] = []
    for record in index["contracts"]:
        result = qualify(root, record)
        findings.extend({"contract": record["contract_id"], "reason": reason}
                        for reason in result["reasons"])
        status = result["status"]
        statuses[status] += 1
        if status != record["status"]:
            raise ValueError(f"reported readiness differs from artifact recomputation: {record['contract_id']}")
    return {"contracts": len(index["contracts"]), "totals": statuses, "findings": findings,
             "note": "Independent recount of artifacts using the authoritative qualification path; reported labels grant no admission."}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    output = root / "scratch/funnel_experiment/engineering/phase6-independent-count.json"
    with output.open("x", encoding="utf-8") as handle:
        result = count(root, root / "scratch/funnel_experiment/engineering/phase6-contract-evidence.json")
        handle.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["totals"]))
