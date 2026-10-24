"""Reviewer-only illustrative replay and pinned V37 native replay entry."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

PINS = {
    "release/manifest.json": "a470e889b701571af653bb30a1d9d3036a828096e8a7370f858d2788f01784eb",
    "anchor.json": "9d8566217753b3fd1187961b0e2009ca81e4b3a16c0f4f25e99a15f165d9f266",
    "quality-context.json": "8233f895f6e58b10ea827b8d16b709aca8a9d36cc1ff56795275882fe075fb80",
    "validate_bound_release_windows.py": "fef7a1557705a997e4e455bb19dcb1dadce913768fc446e44b129715c27f3726",
}
HISTORICAL = {
    "bundled-validation-result.json": "2793c1372b0d0c401d66a57760ed252a3767ef98c1bd89a6645afcc66d4ffe69",
    "relocated-replay-terminal.json": "9698bf96c132db1e93262ec9f67724814c4312969d65f6c59ca0dd1597b497d4",
    "worker-events.jsonl": "eecdb06a105a7655233a4433b0cea774f016c30e910a512bf977115dea9af541",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def io(path):
    text = str(Path(path).resolve())
    return Path("\\\\?\\" + text) if sys.platform == "win32" and not text.startswith("\\\\?\\") else Path(text)


def load(path):
    return json.loads(io(path).read_bytes())


def sha(path):
    return hashlib.sha256(io(path).read_bytes()).hexdigest()


def save(path, data):
    with io(path).open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())


def verify_hash(path, expected):
    require(sha(path) == expected, f"SHA256 mismatch: {path}")


def check_inputs(package, history=None):
    """Small identity/selected-proof check; deliberately not a full trust traversal."""
    for name, digest in PINS.items():
        verify_hash(package / name, digest)
    manifest = load(package / "release/manifest.json")
    require(len(manifest["files"]) == 123765 and manifest["record_count"] == 8, "unexpected release census")
    declared = {f["relative_path"]: f for f in manifest["files"]}
    for name in ("engineering_acceptance.json", "engineering_dependencies.json"):
        verify_hash(package / "release" / name, declared[name]["content_hash"])
    context = load(package / "quality-context.json")
    require(context["manifest_sha256"] == PINS["release/manifest.json"] and
            context["anchor_sha256"] == PINS["anchor.json"], "context identity mismatch")
    verify_hash(package / "release/engineering_acceptance.json", context["acceptance_sha256"])
    require(load(package / "release/engineering_acceptance.json") == context["acceptance"], "context differs")
    result = {"scope": "identity and selected proof inspection only; NOT a new native replay",
              "pins": PINS, "declared_files": len(manifest["files"])}
    if history:
        for name, digest in HISTORICAL.items():
            verify_hash(history / name, digest)
        report = load(history / "bundled-validation-result.json")
        require(report["report"]["status"] == "VALID" and not report["report"]["errors"] and
                report["report"]["record_count"] == 8 and
                report["context_sha256"] == PINS["quality-context.json"], "historical proof differs")
        require(load(history / "relocated-replay-terminal.json")["returncode"] == 0, "historical worker failed")
        result["historical"] = report
    return result


def typed_equal(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def compare(actual, expected):
    return {
        "column_names": [c["name"] for c in actual["columns"]] == [c["name"] for c in expected["columns"]],
        "declared_output_types": [c["type"] for c in actual["columns"]] == [c["type"] for c in expected["columns"]],
        "ordered_typed_rows": typed_equal(actual["rows"], expected["rows"]),
        "rows_returned": typed_equal(actual["rows_returned"], expected["rows_returned"]),
        "truncated": typed_equal(actual["truncated"], expected["truncated"]),
    }


def execute_fixture(fixture):
    import duckdb
    def quote(name):
        return '"' + name.replace('"', '""') + '"'
    with duckdb.connect(":memory:", config={"enable_external_access": "false",
            "autoinstall_known_extensions": "false", "autoload_known_extensions": "false", "threads": "1"}) as con:
        for table in fixture["schema"]:
            columns = []
            for c in table["columns"]:
                dtype = "DECIMAL(18, 2)" if c["type"] == "DECIMAL" else c["type"]
                require(dtype in {"INTEGER", "BIGINT", "HUGEINT", "VARCHAR", "TIMESTAMP", "DATE", "BOOLEAN", "DOUBLE", "DECIMAL(18, 2)"}, "unsupported fixture type")
                columns.append(f'{quote(c["name"])} {dtype}' + ("" if c.get("nullable", True) else " NOT NULL"))
            con.execute(f'CREATE TABLE {quote(table["name"])} ({", ".join(columns)})')
            names = [c["name"] for c in table["columns"]]
            rows = fixture["tables"][table["name"]]
            if rows:
                con.executemany(f'INSERT INTO {quote(table["name"])} VALUES ({",".join("?" for _ in names)})',
                                [[row.get(n) for n in names] for row in rows])
        statements = con.extract_statements(fixture["sql"])
        require(len(statements) == 1 and str(statements[0].type) == "StatementType.SELECT", "one SELECT required")
        cursor = con.execute(fixture["sql"])
        columns = [{"name": d[0], "type": str(d[1])} for d in cursor.description]
        fetched = cursor.fetchmany(10001)
        rows = [[v if v is None or type(v) in (bool, int, float, str) else str(v) for v in row] for row in fetched[:10000]]
        return {"columns": columns, "rows": rows, "rows_returned": len(rows), "truncated": len(fetched) > 10000}


def illustrative(examples):
    entries = load(examples / "index.json")["examples"]
    require([e["example_id"] for e in entries] == [f"{n:02}" for n in range(1, 9)], "exact ordered eight examples required")
    results = []
    for entry in entries:
        relative = Path(entry["fixture"])
        require(not relative.is_absolute() and len(relative.parts) == 1 and ":" not in str(relative), "fixture must be a local filename")
        fixture = load(examples / relative)
        require(all(fixture[k] == entry[k] for k in ("example_id", "candidate_id")), "fixture identity mismatch")
        actual = execute_fixture(fixture)
        comparisons = compare(actual, fixture["expected"])
        results.append({"example_id": entry["example_id"], "candidate_id": entry["candidate_id"],
                        "fixture_sha256": sha(examples / relative), "comparisons": comparisons,
                        "passed": all(comparisons.values()), "actual": actual, "expected": fixture["expected"]})
    import duckdb
    return {"scope": "A: illustrative public/base fixture replay only; NOT authoritative B", "duckdb": duckdb.__version__,
            "passed": all(r["passed"] for r in results), "records": results}


def fresh_directory(path, forbidden):
    path = path.resolve()
    require(not any(path == f.resolve() or path.is_relative_to(f.resolve()) or f.resolve().is_relative_to(path)
                    for f in forbidden), "work/output must be separate from package and each other")
    require(path.parent.is_dir(), "parent directory must already exist")
    path.mkdir(exist_ok=False)
    return path


def validate(args):
    require(sys.platform == "win32", "native supervisor requires Windows Job ownership")
    require(1 <= args.timeout <= 10800, "timeout must be 1..10800 seconds")
    package = args.package.resolve()
    # Both identities must be new before any package copying or native work.
    require(not args.work.exists() and not args.output.exists(), "fresh unique work/output required")
    forbidden = [package, Path(__file__).resolve().parent.parent]
    forbidden += [p for p in Path(__file__).resolve().parents if (p / "AGENTS.md").is_file()]
    require(not any(args.work.resolve().is_relative_to(p) or args.output.resolve().is_relative_to(p)
                    for p in forbidden), "use work/output outside checkout and preview")
    work = fresh_directory(args.work, [package, args.output])
    output = fresh_directory(args.output, [package, work])
    save(output / "identity.json", {"run_id": uuid.uuid4().hex, "work": str(work), "output": str(output), "pins": PINS})
    command = [sys.executable, "-B", "-I", str(Path(__file__).with_name("native_worker.py")), str(work), str(output)]
    from windows_job import Job
    process = None
    began = time.monotonic()
    terminal = {"returncode": None, "timeout": False, "phase": "prepare"}
    try:
        check_inputs(package)
        for folder in ("release", "packet"):
            shutil.copytree(io(package / folder), io(work / folder))
        for name in ("anchor.json", "quality-context.json", "validate_bound_release_windows.py"):
            shutil.copyfile(io(package / name), io(work / name))
        with Job() as job, (output / "stdout.log").open("x", encoding="utf-8") as stdout, (output / "stderr.log").open("x", encoding="utf-8") as stderr:
            process = subprocess.Popen(command, cwd=work, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr)
            try:
                job.assign(process)
                save(output / "launch.json", {"command": command, "pid": process.pid, "supervisor": os.getpid(),
                     "at": time.time(), "timeout_seconds": args.timeout, "ownership": "Windows Job kill-on-close"})
                process.stdin.write(b"GO\n")
                process.stdin.close()
                terminal["phase"] = "native"
                try:
                    terminal["returncode"] = process.wait(timeout=args.timeout)
                except subprocess.TimeoutExpired:
                    terminal.update(timeout=True, returncode=124)
            finally:
                if process.poll() is None:
                    job.kill()
                    process.kill()
                    process.wait(timeout=30)
        require(terminal["returncode"] == 0, "native worker failed; inspect output logs")
    finally:
        terminal.update(elapsed=time.monotonic() - began, pid=process.pid if process else None)
        save(output / "terminal.json", terminal)
    return {"scope": "new B run; inspect bundled-validation-result.json and per-record events", "output": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("illustrative")
    a.add_argument("--examples", type=Path, required=True)
    a.add_argument("--result", type=Path, help="new result file; parent must exist")
    c = sub.add_parser("check-inputs")
    c.add_argument("--package", type=Path, required=True)
    c.add_argument("--history", type=Path)
    b = sub.add_parser("validate")
    b.add_argument("--package", type=Path, required=True)
    b.add_argument("--work", type=Path, required=True)
    b.add_argument("--output", type=Path, required=True)
    b.add_argument("--timeout", type=int, default=7200)
    args = parser.parse_args()
    if args.command == "illustrative":
        result = illustrative(args.examples)
        if args.result:
            save(args.result, result)
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] else 1
    result = check_inputs(args.package, args.history) if args.command == "check-inputs" else validate(args)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError) as exc:
        print(f"Replay refused: {exc}", file=sys.stderr)
        sys.exit(1)
