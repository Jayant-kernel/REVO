"""Append-only operation receipts; an integrity guard, not an OS sandbox.

Only the exact new output directory is permitted. Callers must declare existing
evidence (files or whole directories), including historical runs. Undeclared
trees receive path/stat screening, not full content protection. Commands are trusted local commands: changes
are detected after execution, not prevented by filesystem permissions.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import subprocess
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from verified_data_factory.local_paths import io_path

PROTECTED = ("src", "templates", "scripts", "tests", "configs", "docs", "manifests")
RECORDS = {"launch.json", "post.json", "terminal.json", "receipt.json", "stdout.log", "stderr.log"}
# Git internals and generated interpreter/test/linter caches are volatile, not authority.
VOLATILE = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def _sources(root: Path) -> list[Path]:
    return [_path(root, folder) for folder in PROTECTED] + [
        p for p in root.iterdir() if p.is_file()
        and p.suffix in {".py", ".toml", ".md", ".yaml", ".yml", ".json"}]


def _inventory(root: Path, output: Path) -> dict[str, Any]:
    entries = {}

    def visit(path: Path, info: os.stat_result) -> None:
        if path == output:
            return
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"symbolic/reparse redirection: {path}")
        key = path.relative_to(root).as_posix()
        if stat.S_ISDIR(info.st_mode):
            if path.name in VOLATILE:
                return
            entries[key] = ["directory", info.st_dev, info.st_ino]
            with os.scandir(io_path(path)) as children:
                for child in children:
                    visit(path / child.name, child.stat(follow_symlinks=False))
        elif stat.S_ISREG(info.st_mode):
            entries[key] = ["file", info.st_dev, info.st_ino, info.st_size,
                            info.st_mtime_ns, info.st_ctime_ns]
        else:
            raise ValueError(f"nonregular workspace path: {path}")

    _plain(root)
    with os.scandir(io_path(root)) as children:
        for child in children:
            visit(root / child.name, child.stat(follow_symlinks=False))
    return entries


class _WindowsJob:
    """Assign the suspended child before it can spawn; close kills only this job."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes as w

        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                        ("flags", w.DWORD), ("min_ws", ctypes.c_size_t),
                        ("max_ws", ctypes.c_size_t), ("active", w.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", w.DWORD),
                        ("scheduling", w.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
                        ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                        ("peak_job", ctypes.c_size_t)]

        self.ctypes = ctypes
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.api.CreateJobObjectW.restype = w.HANDLE
        self.api.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.api.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.api.CloseHandle.argtypes = [w.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway.
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def start(self, process: subprocess.Popen) -> None:
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        resume = self.ctypes.WinDLL("ntdll").NtResumeProcess
        resume.argtypes = [self.ctypes.c_void_p]
        resume.restype = self.ctypes.c_long
        if resume(int(process._handle)) != 0:
            raise OSError("cannot resume supervised process")

    def close(self) -> None:
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def _execute(command: Sequence[str], root: Path, timeout: float, stdout, stderr) -> tuple[int | None, bool]:
    job = _WindowsJob() if os.name == "nt" else None
    process = None
    try:
        process = subprocess.Popen(list(command), cwd=root, stdout=stdout, stderr=stderr,
                                   creationflags=0x4 if job else 0,
                                   start_new_session=not bool(job))
        if job:
            job.start(process)
        try:
            return process.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            return None, True
    finally:
        if job:
            job.close()
        elif process:
            import signal
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)


def _path(root: Path, value: str | Path) -> Path:
    raw = Path(value)
    if ".." in raw.parts or (not raw.is_absolute() and raw.drive):
        raise ValueError(f"traversal or drive-relative path: {value}")
    path = raw if raw.is_absolute() else root / raw
    if path == root or not path.is_relative_to(root):
        raise ValueError(f"path must be strictly within root: {value}")
    if any(":" in part for part in path.relative_to(root).parts):
        raise ValueError(f"alternate-stream redirection: {value}")
    _plain(path)
    return path


def _plain(path: Path) -> None:
    # lstat sees dangling links and Windows junctions without following them.
    for component in (*reversed(path.parents), path):
        try:
            info = io_path(component).lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"symbolic/reparse redirection: {component}")


def _sha(path: Path) -> str:
    with io_path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _snapshot(root: Path, paths: Sequence[Path], *, source: bool) -> dict[str, str]:
    entries: dict[str, str] = {}

    def visit(path: Path, info: os.stat_result | None = None) -> None:
        key = path.relative_to(root).as_posix()
        try:
            info = info or io_path(path).lstat()
        except FileNotFoundError:
            entries[key] = "missing"
            return
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"symbolic/reparse redirection: {path}")
        if stat.S_ISDIR(info.st_mode):
            entries[key] = "directory"
            with os.scandir(io_path(path)) as children:
                for child in children:
                    if source and child.name == "__pycache__":
                        continue
                    visit(path / child.name, child.stat(follow_symlinks=False))
        elif stat.S_ISREG(info.st_mode):
            entries[key] = _sha(path)
        else:
            raise ValueError(f"nonregular protected input: {path}")

    for path in paths:
        _plain(path)
        visit(path)
    return entries


def live_guard(root: Path) -> None:
    """Reuse frozen safety and paused-run baseline checks without writing a report."""
    from scripts import engineering_campaign as campaign
    from scripts import package_a_paused_run_guard as paused

    if root != campaign.ROOT:
        raise ValueError("temporary roots require an explicit guard callback")
    campaign.safety()
    run = root / "runs/premium-qualification-080"
    baseline = paused.read_baseline(root / "scratch/paused-run.baseline.sha256.txt")
    actual = {p.relative_to(run).as_posix(): paused.sha256_file(p)
              for p in run.rglob("*") if p.is_file()}
    if len(actual) != 15 or actual != baseline:
        raise ValueError("paused-run guard failed")


def run_guarded(
    root: str | Path,
    output_path: str | Path,
    command: Sequence[str],
    required_outputs: Sequence[str | Path],
    timeout_s: float,
    protected_inputs: Sequence[str | Path] = (),
    *,
    output_boundary: str | Path,
    guard: Callable[[Path], None] = live_guard,
) -> dict[str, Any]:
    """Run once with cwd=root, returning PASS/FAIL/INTERRUPTED and actual outcome.

    ``output_boundary`` must equal the exact new directory, at least three
    components below root. No existing destination or protected-tree overlap is
    allowed. Missing/empty completion files, changed sources/evidence, guard
    errors, launch errors, and timeouts never earn PASS. Rejected post-execution
    redirection returns FAIL without writing through the redirected pathname.
    """
    root = Path(os.path.abspath(root))
    _plain(root)
    if not root.is_dir():
        raise ValueError("root must exist")
    output = _path(root, output_path)
    boundary = _path(root, output_boundary)
    if output != boundary or len(output.relative_to(root).parts) < 3:
        raise ValueError("declare an exact narrow output boundary")
    if output.exists() or not output.parent.is_dir():
        raise ValueError("destination must be fresh with an existing parent")
    if not command or isinstance(command, (str, bytes)):
        raise ValueError("command must be a nonempty argv sequence")
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("timeout must be finite and positive")
    if not protected_inputs:
        raise ValueError("explicit authoritative existing evidence is required")
    sources = _sources(root)
    evidence = [_path(root, p) for p in protected_inputs]
    for protected in (*sources, *evidence):
        if output.is_relative_to(protected) or protected.is_relative_to(output):
            raise ValueError("output overlaps protected input")
    if any(not p.exists() for p in evidence):
        raise ValueError("declared evidence must exist")
    required = [_path(output, p) for p in required_outputs]
    if not required or len(set(required)) != len(required):
        raise ValueError("declare unique completion files")
    if any(p.relative_to(output).parts[0] in RECORDS for p in required):
        raise ValueError("completion files cannot be wrapper records")
    guard(root)
    census_started = time.monotonic()
    before = {"source": _snapshot(root, sources, source=True),
              "evidence": _snapshot(root, evidence, source=False),
              "workspace": _inventory(root, output)}
    pre_census_s = time.monotonic() - census_started
    output.mkdir(exist_ok=False)
    directory_identity = (output.stat().st_dev, output.stat().st_ino)

    def confined() -> None:
        _plain(output)
        if not output.is_dir() or (output.stat().st_dev, output.stat().st_ino) != directory_identity:
            raise ValueError("output directory replaced")
        for path in output.rglob("*"):
            _plain(path)
            if not path.is_dir() and not path.is_file():
                raise ValueError(f"nonregular output: {path}")
            if path.is_file() and io_path(path).stat().st_nlink != 1:
                raise ValueError(f"hard-linked output: {path}")

    def write(name: str, payload: Any) -> None:
        confined()
        with (output / name).open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    write("launch.json", {"at": datetime.now(UTC).isoformat(), "command": list(command),
                          "cwd": str(root), "output_boundary": str(boundary),
                          "required_outputs": [str(p) for p in required],
                           "timeout_s": timeout_s, "identity": before,
                           "pre_census_s": pre_census_s,
                           "volatile_trees": sorted(VOLATILE)})
    launch = output / "launch.json"
    launch_identity = (launch.stat().st_dev, launch.stat().st_ino, _sha(launch))
    errors: list[str] = []
    exit_code = None
    timed_out = False
    log_identities = {}
    try:
        with (output / "stdout.log").open("xb") as stdout, (output / "stderr.log").open("xb") as stderr:
            for name, handle in (("stdout.log", stdout), ("stderr.log", stderr)):
                info = os.fstat(handle.fileno())
                log_identities[name] = (info.st_dev, info.st_ino)
            exit_code, timed_out = _execute(command, root, timeout_s, stdout, stderr)
        if timed_out:
            errors.append("command timed out; completion not accepted")
    except OSError as exc:
        errors.append(f"launch error: {exc}")
    # Terminal outcome is durable before any potentially expensive post-run hashing.
    try:
        write("terminal.json", {"exit_code": exit_code, "timed_out": timed_out})
    except (OSError, ValueError) as exc:
        errors.append(f"terminal persistence error: {exc}")
    after: dict[str, Any] = {}
    census_started = time.monotonic()
    try:
        after = {"source": _snapshot(root, _sources(root), source=True),
                 "evidence": _snapshot(root, evidence, source=False),
                 "workspace": _inventory(root, output)}
        if before != after:
            errors.append("protected source or evidence changed")
        guard(root)
    except Exception as exc:  # noqa: BLE001 -- injected guards must fail closed.
        errors.append(f"post guard error: {exc}")
    post_census_s = time.monotonic() - census_started
    try:
        confined()
        if (launch.stat().st_dev, launch.stat().st_ino, _sha(launch)) != launch_identity:
            errors.append("launch provenance changed")
        for name, identity in log_identities.items():
            info = (output / name).stat()
            if (info.st_dev, info.st_ino) != identity:
                errors.append(f"wrapper log replaced: {name}")
        for name in ("post.json", "receipt.json"):
            if (output / name).exists():
                errors.append(f"command created reserved wrapper record: {name}")
        for path in required:
            _plain(path)
            if not path.is_file() or path.stat().st_size == 0:
                errors.append(f"missing or empty completion file: {path.relative_to(output)}")
    except (OSError, ValueError) as exc:
        errors.append(f"output integrity error: {exc}")
    if exit_code != 0 and not timed_out:
        errors.append(f"command exit code: {exit_code}")
    receipt = {"status": "INTERRUPTED" if timed_out else "FAIL" if errors else "PASS",
               "exit_code": exit_code, "timed_out": timed_out, "errors": errors,
               "identity_match": before == after, "at": datetime.now(UTC).isoformat(),
               "pre_census_s": pre_census_s, "post_census_s": post_census_s}
    try:
        write("post.json", {"identity": after, "identity_match": before == after})
        write("receipt.json", receipt)
    except (OSError, ValueError) as exc:
        errors.append(f"receipt persistence error: {exc}")
        receipt["status"] = "INTERRUPTED" if timed_out else "FAIL"
    return receipt
