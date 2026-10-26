"""Full current-contract, three-seed output diagnostics; never grants readiness."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engineering_campaign import OUT, safety, stamp, write_new

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification.oracle_registry import get_oracle


def main() -> None:
    safety()
    latest = {}
    for template in load_builtin_registry().list():
        if template.template_id not in latest or latest[template.template_id].version < template.version:
            latest[template.template_id] = template
    files = []
    for seed in (1, 43, 94001):
        path = OUT / f"phase7-vacuity-seed-{seed}.csv"
        with path.open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["contract", "version", "seed", "rows", "distinct_values", "empty", "single_row", "all_equal", "reason"])
            writer.writeheader()
            for contract, template in sorted(latest.items()):
                task = generate_task(template, seed)
                expected = get_oracle(contract, template.version).fn(task.requirements, task.tables)
                encoded = [json.dumps(row, sort_keys=True) for row in expected.rows]
                values = {json.dumps(value) for row in expected.rows for value in row}
                empty = len(encoded) == 0
                single = len(encoded) == 1
                equal = bool(encoded) and len(set(encoded)) == 1
                writer.writerow({"contract": contract, "version": template.version, "seed": seed,
                                 "rows": len(encoded), "distinct_values": len(values), "empty": empty,
                                 "single_row": single, "all_equal": equal,
                                 "reason": "low-information output; requires discriminating challenge evidence" if empty or single or equal else "non-vacuous row diversity; semantic discrimination still separately required"})
        files.append(path.name)
    write_new(OUT / "phase7-vacuity-audit.json", {"created_at": stamp(), "contracts": len(latest),
                                               "seeds": [1, 43, 94001], "csvs": files,
                                               "readiness_granted": False})
    print(json.dumps({"contracts": len(latest), "seeds": [1, 43, 94001], "csvs": files}))


if __name__ == "__main__":
    main()
