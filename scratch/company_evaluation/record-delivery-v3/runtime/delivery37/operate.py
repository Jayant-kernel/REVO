"""Bounded V37 original-response delivery; existing product/admission APIs only."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import locale
import os
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.engineering_guarded_operation import _execute
from verified_data_factory.local_paths import io_path
from verified_data_factory.products.isolation import isolation_keys
from verified_data_factory.quality.models import GoldenRecord
from verified_data_factory.sandbox import SandboxExecutor, load_config
from verified_data_factory.verification import verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.readiness import authoritative_records, qualify
from verified_data_factory.verification.receipt_validation import digest


def module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


d = module("retained_delivery36", HERE.parent / "delivery_v36.py")
d.OUT = HERE
d.QUAL = ROOT / "scratch/funnel_experiment/engineering/qualified-receipts-v37"
d.DURABLE = ROOT / "artifacts/internal-deliveries/v37-original8-001"
SUITE = ROOT / "scratch/company_evaluation/record-delivery-v3/workstream-c/full-suite-v37"
OLD_PACKAGE = ROOT / "artifacts/internal-deliveries/v36/original8"
POOL = HERE / "original-pool"


def save(path: Path, value: Any) -> None:
    io_path(path.parent).mkdir(parents=True, exist_ok=True)
    with io_path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())


def check() -> Any:
    frozen = d.stable()
    assert d.usage() == frozen["budget"]
    if (HERE / "preflight.json").exists():
        pre = d.load(HERE / "preflight.json")
        assert digest(d.REGISTRY) == pre["registry_sha256"]
        assert d.trust.inventory(OLD_PACKAGE) == pre["v36_inventory"]
    return frozen


def preflight() -> None:
    frozen = check()
    # Match only the existing suite scope; new operators do not rewrite its manifest.
    from importlib.util import module_from_spec, spec_from_file_location
    spec = spec_from_file_location("retained_suite_runner", SUITE.parent / "runner.py")
    assert spec and spec.loader
    runner = module_from_spec(spec)
    spec.loader.exec_module(runner)
    assert runner.sources() == d.load(SUITE / "source.post.json")
    terminal = d.load(SUITE / "terminal.json")
    assert terminal["status"] == "PASS" and terminal["session_finished"]
    rows = []
    registry = d.load(d.REGISTRY)
    records = {(r["contract_id"], r["contract_version"]): r for r in authoritative_records(ROOT)}
    assert len(records) == 20
    old_members = d.load(OLD_PACKAGE / "packet/membership.json")["members"]
    for index in range(8):
        task, candidate, run, slot = d.original(index)
        golden = GoldenRecord.model_validate(next(m["golden"] for m in old_members
                                                 if m["candidate_id"] == candidate.candidate_id))
        assert golden.candidate_solution == candidate.candidate_sql
        keys = sorted(isolation_keys(golden))
        assert all(registry.get(key) == "TRAIN" for key in keys)
        record = records[task.template_id, task.template_version]
        status = qualify(ROOT, record)
        assert status["eligible"], status
        folder = run / f"attempt-{slot:03d}"
        rows.append({"index": index, "candidate_id": candidate.candidate_id,
                     "task_id": task.task_id, "contract": task.template_id,
                     "version": task.template_version, "role": "TRAIN", "isolation_keys": keys,
                     "request": str((folder / "request.json").relative_to(ROOT)),
                     "response": str((folder / "http-response.json").relative_to(ROOT)),
                     "request_sha256": digest(folder / "request.json"),
                     "response_sha256": digest(folder / "http-response.json"),
                     "sql_sha256": hashlib.sha256(candidate.candidate_sql.encode()).hexdigest(),
                     "qualification": record, "qualification_status": status})
    # Probe the current prerequisite, without elevation or OS changes.
    import tempfile
    privilege: dict[str, Any]
    with tempfile.TemporaryDirectory(prefix="revo-link-probe-", dir=d.TEMP) as temp:
        target = Path(temp) / "target"
        target.mkdir()
        try:
            (Path(temp) / "link").symlink_to(target, target_is_directory=True)
            privilege = {"available": True}
        except OSError as exc:
            privilege = {"available": False, "winerror": exc.winerror, "error": str(exc)}
    save(HERE / "preflight.json", {"source_freeze_sha256": digest(d.QUAL / "freeze.json"),
         "source_hashes": frozen["global_sources"], "budget": d.usage(), "rows": rows,
         "v36_inventory": d.trust.inventory(OLD_PACKAGE), "registry_sha256": digest(d.REGISTRY),
         "suite_terminal": terminal, "symlink_prerequisite": privilege, "at": time.time()})
    print(json.dumps({"status": "PREFLIGHT_PASS", "candidates": 8,
                      "symlink_prerequisite": privilege, "budget": d.usage()}), flush=True)


def retain_five() -> None:
    check()
    pre = d.load(HERE / "preflight.json")
    accounting = d.load(SUITE / "accounting.json")
    launch = d.load(SUITE / "launch.json")
    temp = Path(next(x.split("=", 1)[1] for x in launch["command"] if x.startswith("--basetemp=")))
    paths = []
    for path in temp.glob("test_original_native_verifier_*/verification.json"):
        # Tests used Path.write_text with the Windows locale, not UTF-8.
        result = json.loads(io_path(path).read_text(encoding=locale.getencoding()))
        # Ignore duplicated pytest 'current' aliases, if any.
        if "current" in path.parent.name:
            continue
        paths.append((result["candidate_id"], path))
    assert len(paths) == 5, paths
    retained = []
    for row in pre["rows"]:
        matches = [p for cid, p in paths if cid == row["candidate_id"]]
        if not matches:
            continue
        assert len(matches) == 1
        path = matches[0]
        node = f'tests/test_delivery_adversarial.py::test_original_native_verifier_and_screen[{row["contract"]}]'
        assert next(n for n in accounting["nodes"] if n["nodeid"] == node)["status"] == "passed"
        execution = json.loads(io_path(path.parent / "execution.json").read_text(encoding=locale.getencoding()))
        verification = json.loads(io_path(path).read_text(encoding=locale.getencoding()))
        checkpoint(row["index"], execution, verification, {
            "kind": "retained_final_same_source_suite", "suite_node": node,
            "source_manifest_sha256": launch["source_manifest_sha256"],
            "verification_path": str(path), "verification_sha256": digest(path),
            "execution_path": str(path.parent / "execution.json"),
            "execution_sha256": digest(path.parent / "execution.json")})
        retained.append(row["candidate_id"])
    assert len(retained) == 5
    save(HERE / "retained-five.json", {"candidate_ids": retained, "status": "BOUND_CURRENT"})


def checkpoint(index: int, execution: dict[str, Any], verification: dict[str, Any], evidence: dict[str, Any]) -> None:
    task, candidate, run, slot = d.original(index)
    assert execution["candidate_id"] == verification["candidate_id"] == candidate.candidate_id
    assert execution["task_id"] == verification["task_id"] == task.task_id
    assert verification["execution_id"] == execution["execution_id"]
    cases = [case for case in (verification.get("hidden") or {}).get("cases", [])
             if case["source"] == "INDEPENDENT_ADVERSARIAL"]
    mutation = verification.get("mutation") or {}
    eligible = (execution["status"] == "SUCCEEDED" and verification["verdict"] == "PASS"
                and verification["verification_strength"] == "STRONG"
                and mutation.get("coverage_complete") and mutation.get("mutation_score") == 1.0
                and len(cases) == 1 and cases[0]["status"] == "PASS")
    save(POOL / f"{index:03d}-execution.json", execution)
    save(POOL / f"{index:03d}-verification.json", verification)
    save(POOL / f"{index:03d}-evidence.json", {**evidence,
         "source_freeze_sha256": digest(d.QUAL / "freeze.json"),
         "candidate_id": candidate.candidate_id, "sql_sha256": hashlib.sha256(candidate.candidate_sql.encode()).hexdigest()})
    save(POOL / f"{index:03d}-row.json", {
        "candidate_id": candidate.candidate_id, "task_id": task.task_id, "family": task.family,
        "origin": "LOCAL_MODEL_OUTPUT", "original_run": run.name, "original_slot": slot,
        "generation_status": "SUCCEEDED", "verdict": verification["verdict"],
        "strength": verification["verification_strength"], "partial_strong": bool(eligible),
        "failure_code": verification["failure_code"], "independent_adversarial": cases,
        "generation_content_binding": "PASS", "sampling_binding": "PASS"})
    print(json.dumps({"index": index, "candidate_id": candidate.candidate_id, "eligible": bool(eligible)}), flush=True)


def rejudge(index: int) -> None:
    check()
    assert not (POOL / f"{index:03d}-row.json").exists(), "checkpoint already exists"
    task, candidate, _, _ = d.original(index)
    cfg = load_config(ROOT / "configs/sandbox_production.yaml")
    execution = SandboxExecutor(cfg).execute(task, candidate)
    verification = verify_candidate(task, candidate, execution, backend=DerivedTaskBackend(cfg))
    checkpoint(index, execution.model_dump(mode="json"), verification.model_dump(mode="json"),
               {"kind": "fresh_original_candidate_native_rejudge", "at": time.time()})
    check()


def export() -> None:
    # Export API retains failures; only eligible rows may enter the new package.
    check()
    d.export_originals()


def build() -> None:
    check()
    d.build("original8")
    check()


def prepare_replay() -> None:
    check()
    base = d.DURABLE / "original8"
    work = d.TEMP / "v37-original8-relocated-001"
    assert not work.exists()
    work.mkdir()
    for folder in ("release", "packet"):
        shutil.copytree(io_path(base / folder), io_path(work / folder))
    shutil.copyfile(base / "anchor.json", work / "anchor.json")
    shutil.copyfile(d.DRIVER, work / "validate_bound_release_windows.py")
    acceptance = d.load(base / "release/engineering_acceptance.json")
    context = {"acceptance": acceptance, "acceptance_sha256": digest(base / "release/engineering_acceptance.json"),
               "manifest_sha256": digest(base / "release/manifest.json"), "anchor_sha256": digest(base / "anchor.json")}
    save(HERE / "quality-context.json", context)
    save(HERE / "replay-config.json", {"release": str(work / "release"), "packet": str(work / "packet"),
        "anchor": str(work / "anchor.json"), "driver": str(work / "validate_bound_release_windows.py"),
        "context": str(HERE / "quality-context.json"), "output": str(HERE),
        "manifest_sha256": context["manifest_sha256"], "anchor_sha256": context["anchor_sha256"],
        "context_sha256": digest(HERE / "quality-context.json"), "driver_sha256": digest(d.DRIVER)})


def worker(command: list[str], label: str, seconds: int) -> None:
    job_module = module("retained_recovery", HERE.parent / "recovery-v36/recover.py")
    import subprocess
    began = time.monotonic()
    job = job_module.Job()
    process = None
    try:
        with (HERE / (label + ".log")).open("x", encoding="utf-8") as stream:
            process = subprocess.Popen(command, cwd=d.TEMP, stdin=subprocess.PIPE, stdout=stream, stderr=subprocess.STDOUT)
            job.assign(process)
            assert process.stdin is not None
            save(HERE / (label + "-launch.json"), {"command": command, "pid": process.pid,
                 "supervisor": os.getpid(), "at": time.time(), "timeout_seconds": seconds})
            process.stdin.write(b"GO\n")
            process.stdin.flush()
            process.stdin.close()
            code = process.wait(timeout=seconds)
        save(HERE / (label + "-terminal.json"), {"returncode": code, "elapsed": time.monotonic() - began})
        assert code == 0, label
    finally:
        if process is not None and process.poll() is None:
            job.kernel.TerminateJobObject(job.handle, 124)
            process.wait(timeout=30)
        job.close()


def replay() -> None:
    check()
    worker([sys.executable, "-B", str(HERE.parent / "recovery-v36/validate_worker.py"),
            str(HERE / "replay-config.json")], "relocated-replay", 7200)
    result = d.load(HERE / "bundled-validation-result.json")["report"]
    assert result["status"] == "VALID" and result["record_count"] == 8
    assert not result["errors"] and not result["warnings"]
    base = d.DURABLE / "original8"
    shutil.copyfile(HERE / "quality-context.json", base / "quality-context.json")
    shutil.copyfile(d.DRIVER, base / "validate_bound_release_windows.py")
    manifest = d.load(base / "release/manifest.json")
    typed = [d.TrainingRecord.model_validate(row).model_dump(mode="json", by_alias=True)
             for shard in manifest["shards"] for row in d.read_jsonl(io_path(base / "release" / shard["relative_path"]))]
    members = d.load(base / "packet/membership.json")["members"]
    assert len(typed) == len(members) == 8
    for row in typed:
        m = next(m for m in members if m["record_id"] == row["golden_record_id"])
        assert row["sql"] == m["golden"]["candidate_solution"]
        assert row["task_id"] == m["golden"]["task"]["task_id"]
    d.write_jsonl(typed, HERE / "typed-records.jsonl")
    d.write_parquet(typed, HERE / "typed-records.parquet")
    assert d.read_jsonl(HERE / "typed-records.jsonl") == d.read_parquet(HERE / "typed-records.parquet") == typed
    save(HERE / "typed-roundtrip.json", {"exact_rows": 8, "status": "PASS"})
    save(HERE / "durable-inventory.json", d.trust.inventory(base))
    check()


def negatives() -> None:
    check()
    base = d.DURABLE / "original8"
    out = HERE / "negative-controls"
    out.mkdir()
    save(HERE / "negative-config.json", {"output": str(out), "base": str(base),
         "driver": str(base / "validate_bound_release_windows.py"), "registry": str(d.REGISTRY),
         "registry_sha256": digest(d.REGISTRY), "manifest_sha256": digest(base / "release/manifest.json"),
         "anchor_sha256": digest(base / "anchor.json")})
    worker([sys.executable, "-B", str(HERE.parent / "recovery-v36/negative_worker.py"),
            str(HERE / "negative-config.json")], "negatives", 900)
    assert d.trust.inventory(base) == d.load(HERE / "durable-inventory.json")
    check()


def execute(action: str, index: int | None = None) -> None:
    if action == "preflight":
        preflight()
    elif action == "retain-five":
        retain_five()
    elif action == "rejudge":
        assert index is not None
        rejudge(index)
    else:
        {"export": export, "build": build, "prepare-replay": prepare_replay,
         "replay": replay, "negatives": negatives}[action]()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action")
    parser.add_argument("--index", type=int)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    if args.worker:
        execute(args.action, args.index)
        return
    label = args.action + ("-" + str(args.index) if args.index is not None else "")
    if (HERE / (label + "-command.json")).exists():
        label += "-" + str(time.time_ns())
    command = [sys.executable, "-B", str(Path(__file__)), args.action, "--worker"]
    if args.index is not None:
        command += ["--index", str(args.index)]
    begin = time.monotonic()
    save(HERE / (label + "-command.json"), {"command": command, "supervisor": os.getpid(),
         "at": time.time(), "timeout_seconds": 10800})
    with (HERE / (label + ".stdout.log")).open("x") as stdout, (HERE / (label + ".stderr.log")).open("x") as stderr:
        code, timed = _execute(command, ROOT, 10800, stdout, stderr)
    result = {"action": label, "returncode": code, "timeout": timed, "elapsed": time.monotonic() - begin}
    save(HERE / (label + "-action-terminal.json"), result)
    print(json.dumps(result), flush=True)
    assert code == 0 and not timed


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        raise
