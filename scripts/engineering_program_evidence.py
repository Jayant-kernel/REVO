"""Append-only local engineering command evidence with launch/post identities."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.engineering_campaign import FROZEN, MEASUREMENT, ROOT, identity, safety
from scripts.package_a_paused_run_guard import read_baseline, sha256_file


def capture() -> dict[str, Any]:
    safety()
    run = ROOT / "runs/premium-qualification-080"
    baseline = read_baseline(ROOT / "scratch/paused-run.baseline.sha256.txt")
    actual = {p.relative_to(run).as_posix(): sha256_file(p) for p in run.rglob("*") if p.is_file()}
    if len(actual) != 15 or actual != baseline:
        raise ValueError("paused-run 15-file guard failed")
    return {
        "captured_at": datetime.now(UTC).isoformat(),
        "source": identity(),
        "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "git_status": subprocess.check_output(["git", "status", "-sb"], cwd=ROOT, text=True),
        "runtime": {"python": platform.python_version(), "executable": sys.executable,
                    "platform": platform.platform(),
                    "packages": {name: importlib.metadata.version(name) for name in
                                 ("duckdb", "pydantic", "pytest", "hypothesis", "pyarrow")}},
        "frozen": {p: sha256_file(ROOT / p) for p in (*FROZEN, *MEASUREMENT,
                   "scratch/funnel_experiment/engineering/phase0-lock.json")},
        "paused_run": {"status": "PASS", "files": actual},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--stage", type=int, choices=range(1, 8), required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    before = capture()
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "launch.json").write_text(json.dumps(before, indent=2), encoding="utf-8")
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    returncode = 0
    if command:
        with (destination / "terminal.log").open("x", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
        returncode = result.returncode
    after = capture()
    (destination / "post.json").write_text(json.dumps(after, indent=2), encoding="utf-8")
    source_keys = ("git_head", "tracked_diff_sha256", "untracked_source_content_manifest_sha256",
                   "per_file_manifest_sha256")
    same = all(before["source"][key] == after["source"][key] for key in source_keys)
    receipt = {"stage": args.stage, "command": command, "exit_code": returncode,
               "started_at": before["captured_at"], "completed_at": after["captured_at"],
               "source_identity_match": same,
               "status": "PASS" if returncode == 0 and same else "FAIL",
               "scope": "command and guard evidence only; no whole-stage certification"}
    (destination / "receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))
    return 0 if returncode == 0 and same else 1


if __name__ == "__main__":
    raise SystemExit(main())
