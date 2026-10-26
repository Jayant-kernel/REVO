"""Verify the immutable paused run against its forward SHA-256 baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_output(*command: str) -> str:
    return subprocess.check_output(command, text=True, encoding="utf-8").strip()


def source_identity(root: Path) -> dict[str, object]:
    tracked_diff = subprocess.check_output(
        ["git", "diff", "--binary", "HEAD"], cwd=root
    )
    untracked = command_output(
        "git", "-C", str(root), "ls-files", "--others", "--exclude-standard"
    )
    manifest = "\n".join(sorted(filter(None, untracked.splitlines()))) + "\n"
    source_prefixes = ("configs/", "docs/", "manifests/", "scripts/", "src/", "templates/", "tests/")
    content_entries = []
    for relative_path in sorted(filter(None, untracked.splitlines())):
        normalized = relative_path.replace("\\", "/")
        if normalized.startswith(source_prefixes):
            content_entries.append(f"{normalized}  {sha256_file(root / normalized)}")
    tracked_or_untracked_root_files = sorted(path for path in root.iterdir() if path.is_file())
    for path in tracked_or_untracked_root_files:
        content_entries.append(f"{path.name}  {sha256_file(path)}")
    content_manifest = "\n".join(content_entries) + "\n"
    return {
        "git_head": command_output("git", "-C", str(root), "rev-parse", "HEAD"),
        "tracked_diff_sha256": hashlib.sha256(tracked_diff).hexdigest(),
        "untracked_manifest_sha256": hashlib.sha256(manifest.encode()).hexdigest(),
        "untracked_source_content_manifest_sha256": hashlib.sha256(
            content_manifest.encode()
        ).hexdigest(),
    }


def read_baseline(path: Path) -> dict[str, str]:
    baseline: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        digest, separator, relative_path = line.partition("  ")
        if not separator or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"invalid baseline line {line_number}")
        if relative_path in baseline:
            raise ValueError(f"duplicate baseline path: {relative_path}")
        baseline[relative_path] = digest
    return baseline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    run_root = root / "runs" / "premium-qualification-080"
    baseline_path = root / "scratch" / "paused-run.baseline.sha256.txt"
    baseline = read_baseline(baseline_path)
    actual_files = sorted(
        path.relative_to(run_root).as_posix()
        for path in run_root.rglob("*")
        if path.is_file()
    )
    actual = {relative_path: sha256_file(run_root / relative_path) for relative_path in actual_files}
    missing = sorted(set(baseline) - set(actual))
    unexpected = sorted(set(actual) - set(baseline))
    mismatched = sorted(
        relative_path
        for relative_path in set(actual) & set(baseline)
        if actual[relative_path] != baseline[relative_path]
    )
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "baseline_path": baseline_path.relative_to(root).as_posix(),
        "expected_file_count": len(baseline),
        "actual_file_count": len(actual),
        "missing": missing,
        "unexpected": unexpected,
        "mismatched": mismatched,
        "status": "PASS" if len(actual) == 15 and not (missing or unexpected or mismatched) else "FAIL",
        "source_tree_identity": source_identity(root),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
