"""Fresh all-contract campaign outcomes with explicit survivor dispositions."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engineering_campaign import OUT, ROOT, safety, stamp, write_new
from engineering_rejudge import conformance
from engineering_score import digest


def main() -> None:
    safety()
    records = conformance()
    survivors = []
    for record in records:
        for mutant in record.get("mutation", {}).get("details", []):
            if mutant["classification"] == "SURVIVED":
                counterexample = next((other for other in records if other["contract"] == record["contract"]
                    and other["version"] == record["version"] and any(
                        detail["operator"] == mutant["operator"] and detail["sql_sha256"] == mutant["sql_sha256"]
                        and detail["classification"] == "SEMANTIC_KILL" for detail in other.get("mutation", {}).get("details", []))), None)
                survivors.append({"contract_id": record["contract"], "contract_version": record["version"],
                                  "fixture": record["fixture"], "operator": mutant["operator"],
                                  "sql_sha256": mutant["sql_sha256"], "disposition": "COUNTEREXAMPLE_WITNESSED" if counterexample else "OPEN_COVERAGE_FINDING",
                                  "counterexample_fixture": counterexample["fixture"] if counterexample else None,
                                  "qualification_allowed": False,
                                  "reason": "matched this fixture; same SQL hash killed on recorded alternate fixture" if counterexample else "no valid-domain equivalence or counterexample established"})
    write_new(OUT / "phase7-survivors-r1.json", {"created_at": stamp(), "campaigns": records, "survivors": survivors,
                                            "survivor_count": len(survivors), "every_survivor_has_disposition": True,
                                            "source_hashes": {p: digest(ROOT / p) for p in (
                                                "src/verified_data_factory/verification/mutations.py",
                                                "src/verified_data_factory/verification/comparator.py",
                                                "scripts/engineering_rejudge.py", "scripts/engineering_survivors.py")}})
    print(json.dumps({"campaigns": len(records), "open_survivors": len(survivors)}))


if __name__ == "__main__":
    main()
