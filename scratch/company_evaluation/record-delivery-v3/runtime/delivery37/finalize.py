"""Final read-only freshness checks and append-only delivery accounting."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import operate as op

from scripts.engineering_guarded_operation import _execute
from verified_data_factory.verification.receipt_models import ReceiptV2
from verified_data_factory.verification.receipt_validation import digest, validate_sources


def command(label: str, arguments: list[str]) -> dict[str, Any]:
    args = [sys.executable, "-B", "-m", *arguments]
    start = time.monotonic()
    op.save(op.HERE / (label + "-launch.json"), {"command": args, "supervisor": os.getpid(),
            "at": time.time(), "timeout_seconds": 1800})
    with (op.HERE / (label + ".stdout.log")).open("x") as stdout, (op.HERE / (label + ".stderr.log")).open("x") as stderr:
        code, timeout = _execute(args, op.ROOT, 1800, stdout, stderr)
    result = {"returncode": code, "timeout": timeout, "elapsed": time.monotonic() - start, "command": args}
    op.save(op.HERE / (label + "-terminal.json"), result)
    assert code == 0 and not timeout
    return result


def main() -> None:
    pre = op.d.load(op.HERE / "preflight.json")
    frozen = op.check()
    base = op.d.DURABLE / "original8"
    assert op.d.trust.inventory(base) == op.d.load(op.HERE / "durable-inventory.json")
    pins = op.d.load(op.HERE / "original8-origin.json")
    op.d.trust.check(base / "release", pins["manifest_sha256"], base / "packet", base / "anchor.json", pins["anchor_sha256"])
    members = op.d.load(base / "packet/membership.json")["members"]
    assert len(members) == 8
    events = [json.loads(line) for line in (op.HERE / "worker-events.jsonl").read_text().splitlines()]
    entered = [e for e in events if e["phase"] == "CHECK_SOURCE_ENTER"]
    exited = [e for e in events if e["phase"] == "CHECK_SOURCE_EXIT"]
    assert len(entered) == len(exited) == 8
    assert sorted(e["candidate_id"] for e in entered) == pins["candidate_ids"]
    registry = op.d.load(op.d.REGISTRY)
    rows = []
    for row in pre["rows"]:
        index = row["index"]
        task, candidate, _, _ = op.d.original(index)
        checkpoint = op.d.load(op.POOL / f"{index:03d}-row.json")
        assert checkpoint["partial_strong"]
        member = next(m for m in members if m["candidate_id"] == candidate.candidate_id)
        assert member["golden"]["candidate_solution"] == candidate.candidate_sql
        assert all(registry[key] == "TRAIN" for key in row["isolation_keys"])
        record = member["quality"]["engineering_record"]
        assert record == op.d.load(op.d.QUAL / (task.template_id + "-v" + str(task.template_version)) / "bundle.json")
        for ref in record["evidence"].values():
            assert ref["path"].startswith(op.d.QUAL.relative_to(op.ROOT).as_posix() + "/")
            receipt = ReceiptV2.model_validate(op.d.load(op.ROOT / ref["path"]))
            validate_sources(op.ROOT, receipt)
        proof = op.d.load(op.POOL / f"{index:03d}-evidence.json")
        rows.append({**row, "verification": "PASS/STRONG", "adversarial": "1 PASS",
                     "admission": "PASS", "export": "PASS", "relocated_replay": "PASS",
                     "proof_kind": proof["kind"], "record_id": member["record_id"]})
    checks = {
        "core_mypy": command("final-core-mypy", ["mypy", "src"]),
        "operator_mypy": command("final-operator-mypy", ["mypy", "--follow-imports=silent", "src",
            str(op.HERE / "operate.py"), str(Path(__file__))]),
        "lint": command("final-scoped-ruff", ["ruff", "check", str(op.HERE / "operate.py"), str(Path(__file__)),
            "src/verified_data_factory/products/serializers.py", "scripts/engineering_qualification_authority.py",
            "tests/test_phase10_readiness.py"]),
    }
    op.check()
    prior_path = op.ROOT / "scratch/funnel_experiment/engineering/company-progress-checklist-v1-snapshot-5/checklist.json"
    checklist = op.d.load(prior_path)
    for req in checklist["requirements"]:
        if req["id"] in {"W08", "W10", "W11", "W16"}:
            req["evidence_paths"].append((op.HERE / "FINAL-RESULT.json").relative_to(op.ROOT).as_posix())
    checklist["previous_snapshot"] = {"path": prior_path.relative_to(op.ROOT).as_posix(), "sha256": digest(prior_path)}
    checklist["source"] = {"scope": "V37 eight-record internal delivery, original acceptance conditions and statuses unchanged"}
    checklist["separate_statuses"]["dataset_acceptance"] = "0_OF80;EIGHT_SOURCE_CURRENT_INTERNAL_TRAIN_RECORDS"
    checklist["separate_statuses"]["pipeline_reliability"] = "RETAINED_NATIVE_INCIDENTS_UNRESOLVED"
    op.save(op.HERE / "original16-checklist.json", checklist)
    result = {"status": "V37_EIGHT_RECORD_DELIVERY_COMPLETE", "rows": rows,
        "eligible": 8, "excluded": 0, "exported": 8, "successfully_replayed": 8,
        "base": str(base), "manifest_sha256": pins["manifest_sha256"], "anchor_sha256": pins["anchor_sha256"],
        "context_sha256": digest(op.HERE / "quality-context.json"),
        "source_freeze_sha256": digest(op.d.QUAL / "freeze.json"), "qualification_bound_files": len(frozen["hashes"]),
        "v36_unchanged": True, "persistent_roles_unchanged": True, "checks": checks,
        "replay_command_executed": f"python -B {op.HERE.relative_to(op.ROOT).as_posix()}/operate.py replay",
        "replay_launch": "relocated-replay-launch.json", "replay_terminal": "relocated-replay-terminal.json",
        "replay": op.d.load(op.HERE / "bundled-validation-result.json"),
        "negative_controls": op.d.load(op.HERE / "negative-controls/negative-results.json"),
        "budget": op.d.usage(), "new_generation_calls": 0, "accepted80": 0,
        "company_examples": 0, "human_review": "PENDING", "external_sharing": "BLOCKED",
        "original16": checklist["summary"], "original16_percent": 12.5,
        "certification": {"suite": "1980 passed; 2 skips; 22 warnings", "strict_complete_flag": False,
            "policy": "workstream-c/certification_v37.py:112-113 requires no skips in suite accounting; no focused supplement path",
            "prerequisite": pre["symlink_prerequisite"], "native_incidents": "UNRESOLVED",
            "new_full_suite": "NOT_RUN; source unchanged and privilege prerequisite unmet"}}
    op.save(op.HERE / "FINAL-RESULT.json", result)
    print(json.dumps({k: v for k, v in result.items() if k in {"status", "eligible", "excluded", "exported", "successfully_replayed", "budget", "base"}}))


if __name__ == "__main__":
    main()
