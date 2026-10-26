"""Read-only overlap of demoted current contracts and paused Golden rows."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engineering_campaign import OUT, ROOT, safety, write_new


def main() -> None:
    safety()
    records = json.loads((OUT / "phase4-rules.json").read_text())["contracts"]
    demoted = {(r["contract_id"], r["contract_version"]) for r in records if r["status"] == "QUARANTINED"}
    path = ROOT / "runs/premium-qualification-080/quality/export/golden.jsonl"
    goldens = [json.loads(line) for line in path.read_text().splitlines() if line]
    affected = [g["record_id"] for g in goldens if (g["task"]["template_id"], g["task"]["template_version"]) in demoted]
    write_new(OUT / "phase4-paused-overlap.json", {"mode": "READ_ONLY", "goldens": len(goldens),
                                                  "affected_count": len(affected), "affected_record_ids": affected})
    print(json.dumps({"goldens": len(goldens), "affected": len(affected)}))


if __name__ == "__main__":
    main()
