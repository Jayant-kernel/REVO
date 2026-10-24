"""Fresh-location bounded preview integration, retaining every command/terminal."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PREVIEW = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.engineering_guarded_operation import _execute

TEMP = Path(r"C:\Users\jayan\AppData\Local\Temp\opencode")
CLONE = TEMP / "review-preview37-copy-001"
PACKAGE = ROOT / "artifacts/internal-deliveries/v37-original8-001/original8"


def save(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)


def run(label, command, cwd, timeout):
    began = time.monotonic()
    save(PREVIEW / "audit" / (label + "-launch.json"), {
        "command": command, "cwd": str(cwd), "timeout_seconds": timeout,
        "supervisor_pid": os.getpid(), "started_at": time.time()})
    with (PREVIEW / "audit" / (label + ".stdout.log")).open("x", encoding="utf-8") as stdout, (PREVIEW / "audit" / (label + ".stderr.log")).open("x", encoding="utf-8") as stderr:
        code, timed = _execute(command, cwd, timeout, stdout, stderr)
    result = {"returncode": code, "timeout": timed, "elapsed_seconds": time.monotonic() - began}
    save(PREVIEW / "audit" / (label + "-terminal.json"), result)
    print(json.dumps({"action": label, **result}), flush=True)
    assert code == 0 and not timed


def main():
    assert not CLONE.exists()
    CLONE.mkdir()
    hashes = {}
    for folder in ("examples", "replay", "review"):
        shutil.copytree(PREVIEW / folder, CLONE / folder, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(PREVIEW / "START-HERE.md", CLONE / "START-HERE.md")
    for path in CLONE.rglob("*"):
        if path.is_file():
            hashes[path.relative_to(CLONE).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    save(PREVIEW / "audit" / "fresh-copy.json", {"clone": str(CLONE), "files": hashes})
    run("focused", [sys.executable, "-B", str(PREVIEW / "replay/test_replay.py")], ROOT, 180)
    run("illustrative", [sys.executable, "-B", str(CLONE / "replay/replay.py"), "illustrative",
         "--examples", str(CLONE / "examples"), "--result", str(CLONE / "illustrative-results-001.json")], CLONE, 180)
    run("check-inputs", [sys.executable, "-B", str(CLONE / "replay/replay.py"), "check-inputs",
         "--package", str(PACKAGE)], CLONE, 180)
    run("native", [sys.executable, "-B", str(CLONE / "replay/replay.py"), "validate", "--package", str(PACKAGE),
         "--work", str(TEMP / "preview37-work-001"), "--output", str(TEMP / "preview37-result-001"),
         "--timeout", "7200"], CLONE, 10800)
    output = TEMP / "preview37-result-001"
    result = json.loads((output / "bundled-validation-result.json").read_bytes())
    records = json.loads((output / "per-record-results.json").read_bytes())
    assert result["report"]["status"] == "VALID"
    assert len(records) == 8 and all(r["status"] == "PASS" for r in records.values())
    # Retain generated results in evidence, not in the reviewer presentation layer.
    shutil.copyfile(CLONE / "illustrative-results-001.json", PREVIEW / "audit/illustrative-results.json")
    for file in output.iterdir():
        if file.is_file():
            shutil.copyfile(file, PREVIEW / "audit" / ("native-" + file.name))
    save(PREVIEW / "audit/integration-result.json", {"status": "PASS", "illustrative": 8,
         "authoritative": 8, "fresh_copy": str(CLONE), "work": str(TEMP / "preview37-work-001"),
         "output": str(output), "package_dependency": str(PACKAGE),
         "original_checkout_imports": False, "local_dependency_package_required": True,
         "cache_dependency": "installed pinned runtimes and existing Docker sandbox/image; no auto-download authorized"})


if __name__ == "__main__":
    main()
