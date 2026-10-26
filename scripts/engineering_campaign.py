"""Serial engineering campaign lock, baseline and phase certification receipts."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engineering_score import check_lock, digest
from package_a_evidence import source_tree_identity

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "scratch/funnel_experiment/engineering"
MEASUREMENT = (
    "docs/production/engineering-rubric.md", "configs/package_a/engineering-rubric.json",
    "scripts/engineering_score.py", "tests/test_engineering_score.py",
)
FROZEN = (
    "configs/production/premium_qualification_80.yaml", "configs/quality_premium_93.yaml",
    "docs/release-93-spec.md", "scratch/paused-run.baseline.sha256.txt",
)


def stamp() -> str:
    return datetime.now(UTC).isoformat()


def write_new(path: Path, payload: Any) -> None:
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, indent=2) + "\n")


def freeze() -> None:
    OUT.mkdir(exist_ok=True)
    lock_path = OUT / "phase0-lock.json"
    if lock_path.exists():
        check_lock(ROOT, json.loads(lock_path.read_text()))
        return
    write_new(lock_path, {"created_at": stamp(), "rubric_version": "engineering-1.0",
                         "measurement_sources": {p: digest(ROOT / p) for p in MEASUREMENT},
                         "frozen_assets": {p: digest(ROOT / p) for p in FROZEN}})


def safety() -> None:
    lock = json.loads((OUT / "phase0-lock.json").read_text())
    check_lock(ROOT, lock)
    for relative, expected in lock["frozen_assets"].items():
        if digest(ROOT / relative) != expected:
            raise ValueError(f"frozen asset changed: {relative}")


def baseline() -> None:
    safety()
    output = OUT / "phase0-baseline.json"
    if output.exists():
        raise ValueError("baseline already recorded; preserve it")
    readiness = json.loads((ROOT / "manifests/phase3-contract-readiness.json").read_text())
    collect = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=ROOT,
                             capture_output=True, text=True, encoding="utf-8", check=True)
    (OUT / "phase0-collection.log").write_text(collect.stdout + collect.stderr, encoding="utf-8")
    totals = re.findall(r"(\d+) tests? collected", collect.stdout)
    if not totals:
        raise ValueError("test collection has no terminal total")
    run = ROOT / "runs/premium-qualification-080"
    payload = {"measured_at": stamp(), "lock_sha256": digest(OUT / "phase0-lock.json"),
               "contract_readiness_counts": dict(Counter(c["status"] for c in readiness["contracts"])),
               "readiness_is_historical_not_strict": True, "test_count": int(totals[-1]),
               "frozen_run_files": {p.relative_to(run).as_posix(): digest(p) for p in sorted(run.rglob("*")) if p.is_file()}}
    write_new(output, payload)
    print(json.dumps(payload, indent=2))


def identity() -> dict[str, Any]:
    files: dict[str, str] = {}
    for folder in ("src", "tests", "scripts", "configs", "templates", "docs", "manifests"):
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix in (".py", ".yaml", ".json", ".md", ".toml"):
                files[path.relative_to(ROOT).as_posix()] = digest(path)
    for path in sorted((ROOT / "scratch").rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and (
            path.suffix == ".py" or ("threshold" in path.name and path.suffix == ".json")
        ):
            files[path.relative_to(ROOT).as_posix()] = digest(path)
    for path in ROOT.iterdir():
        if path.is_file():
            files[path.name] = digest(path)
    return {**source_tree_identity(ROOT), "per_file_manifest": files,
            "per_file_manifest_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}


def certify(phase: str) -> None:
    safety()
    prefix = OUT / f"phase{phase}"
    paths = {name: Path(str(prefix) + "-" + name) for name in
             ("launch.json", "post.json", "regression.log", "guard.json", "certification.json")}
    if paths["certification.json"].exists():
        raise ValueError("certification exists; use a new retry suffix, never overwrite")
    for path in paths.values():
        path.touch(exist_ok=False)
    before = identity()
    paths["launch.json"].write_text(json.dumps({"captured_at": stamp(), "identity": before}, indent=2), encoding="utf-8")
    with paths["regression.log"].open("w", encoding="utf-8") as log:
        result = subprocess.run([sys.executable, "-m", "pytest", "--durations=25"], cwd=ROOT,
                                stdout=log, stderr=subprocess.STDOUT, check=False)
    after = identity()
    paths["post.json"].write_text(json.dumps({"captured_at": stamp(), "identity": after}, indent=2), encoding="utf-8")
    guard = subprocess.run([sys.executable, "scripts/package_a_paused_run_guard.py", "--output", str(paths["guard.json"])], cwd=ROOT, capture_output=True, text=True, check=False)
    safety()
    summary = paths["regression.log"].read_text(encoding="utf-8").splitlines()[-1]
    report = {"phase": phase, "completed_at": stamp(), "regression_exit_code": result.returncode,
              "terminal_summary": summary, "identity_match": before == after,
              "guard_exit_code": guard.returncode, "lock_sha256": digest(OUT / "phase0-lock.json"),
              "status": "PASS" if result.returncode == guard.returncode == 0 and before == after and "skipped" not in summary else "FAIL"}
    paths["certification.json"].write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


def focused(label: str, tests: list[str]) -> None:
    safety()
    path = OUT / f"{label}-focused.log"
    with path.open("x", encoding="utf-8") as log:
        result = subprocess.run([sys.executable, "-m", "pytest", *tests, "-q"], cwd=ROOT,
                                stdout=log, stderr=subprocess.STDOUT, check=False)
    print(path.read_text(encoding="utf-8"))
    write_new(OUT / f"{label}-focused.json", {"recorded_at": stamp(), "tests": tests,
                                           "exit_code": result.returncode, "log_sha256": digest(path)})
    if result.returncode:
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("freeze", "baseline", "certify", "focused"))
    parser.add_argument("--phase")
    parser.add_argument("--tests", nargs="+")
    args = parser.parse_args()
    if args.action == "freeze":
        freeze()
    elif args.action == "baseline":
        baseline()
    elif args.action == "focused":
        if not args.phase or not re.fullmatch(r"[a-zA-Z0-9-]+", args.phase) or not args.tests:
            raise ValueError("focused test label and paths required")
        focused(args.phase, args.tests)
    else:
        if not args.phase or not re.fullmatch(r"[0-9]+(?:r[0-9]+)?", args.phase):
            raise ValueError("certification phase must be numeric with an optional retry suffix")
        certify(args.phase)


if __name__ == "__main__":
    main()
