"""All-current-contract fixture/result diversity, including reconstructed old behavior."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engineering_campaign import OUT, ROOT, safety, stamp, write_new
from engineering_score import digest

from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.hidden_fixtures import fixture_fingerprint
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.hidden import derive_hidden_seed
from verified_data_factory.verification.models import VERIFICATION_CONFIG_VERSION
from verified_data_factory.verification.oracle_registry import get_oracle


def main() -> None:
    safety()
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default="")
    args = parser.parse_args()
    if args.revision and not re.fullmatch(r"r[0-9]+", args.revision):
        raise ValueError("revision must be r followed by digits")
    threshold = json.loads((ROOT / "configs/package_a/engineering-rubric.json").read_text())
    minimum = threshold["thresholds"]["minimum_distinct_fixtures_including_original"]
    latest = {}
    for template in load_builtin_registry().list():
        if template.template_id not in latest or latest[template.template_id].version < template.version:
            latest[template.template_id] = template
    backend = DerivedTaskBackend()
    records = []
    for _, template in sorted(latest.items()):
        for seed in (1, 43, 94001):
            task = generate_task(template, seed)
            current = [task.tables] + [backend.hidden_tables(task, derive_hidden_seed(seed, VERIFICATION_CONFIG_VERSION, i)) for i in range(3)]
            previous = [task.tables] + [generate_task(template, derive_hidden_seed(seed, "1.1-adversarial", i)).tables for i in range(3)]
            content = [fixture_fingerprint(task, tables) for tables in current]
            old_content = [fixture_fingerprint(task, tables) for tables in previous]
            expected = [get_oracle(task.template_id, task.template_version).fn(task.requirements, tables) for tables in current]
            results = [hashlib.sha256(json.dumps(e.model_dump(mode="json"), sort_keys=True).encode()).hexdigest() for e in expected]
            records.append({"contract": task.template_id, "version": task.template_version, "original_seed": seed,
                            "previous_distinct_contents": len(set(old_content)), "distinct_contents": len(set(content)),
                            "distinct_results": len(set(results)), "fixture_hashes": content,
                            "row_counts": [sum(len(rows) for rows in tables.values()) for tables in current],
                            "result_row_counts": [len(e.rows) for e in expected],
                            "passes_content_floor": len(set(content)) >= minimum})
    report = {"created_at": stamp(), "minimum": minimum, "seeds": [1, 43, 94001], "contracts": len(latest),
              "records": records, "status": "PASS" if all(r["passes_content_floor"] for r in records) else "FAIL",
              "previous_behavior": "Reconstructed generator-only 1.1-adversarial behavior; not a historical byte attestation",
              "independence": "differential verification",
              "source_hashes": {p: digest(ROOT / p) for p in (
                  "scripts/engineering_hidden_audit.py", "src/verified_data_factory/task_engine/hidden_fixtures.py",
                  "src/verified_data_factory/verification/backend.py", "src/verified_data_factory/verification/hidden.py",
                  "src/verified_data_factory/verification/models.py", "configs/package_a/engineering-rubric.json")}}
    suffix = "-" + args.revision if args.revision else ""
    write_new(OUT / f"phase3-diversity{suffix}.json", report)
    print(json.dumps({"status": report["status"], "contracts": len(latest), "contract_seed_cases": len(records),
                      "previous_deficient_cases": sum(r["previous_distinct_contents"] < minimum for r in records),
                      "current_deficient_cases": sum(not r["passes_content_floor"] for r in records)}, indent=2))


if __name__ == "__main__":
    main()
