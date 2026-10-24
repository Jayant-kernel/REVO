"""Exact-context bundled validation, started only by the bounded supervisor."""
import faulthandler
import importlib.util
import json
import os
import sys
import time
import traceback
from pathlib import Path

# -I excludes the script directory: explicitly load this reviewer's sibling only.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from replay import PINS, check_inputs, load, require, save, verify_hash


def main():
    require(sys.stdin.readline().strip() == "GO", "supervisor must assign owned Windows Job first")
    work, output = map(Path, sys.argv[1:])
    def event(phase, **fields):
        value = dict(pid=os.getpid(), at=time.time(), phase=phase, **fields)
        with (output / "worker-events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        print(json.dumps(value), flush=True)
    event("EXTERNAL_TRUST_START")
    check_inputs(work)
    driver = work / "validate_bound_release_windows.py"
    verify_hash(driver, PINS[driver.name])
    spec = importlib.util.spec_from_file_location("pinned_trust", driver)
    trust = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trust)
    release = work / "release"
    trust.check(release, PINS["release/manifest.json"], work / "packet", work / "anchor.json", PINS["anchor.json"])
    context = load(work / "quality-context.json")
    acceptance = load(release / "engineering_acceptance.json")
    membership = load(work / "packet/membership.json")
    def members(data):
        rows = data["members"]
        result = {m["golden"]["record_id"]: (m["golden"], m["quality"]) for m in rows}
        require(len(rows) == len(result) == 8, "exact eight unique members required")
        return result
    require(members(membership) == members(acceptance), "packet/acceptance members differ")
    require(acceptance == context["acceptance"], "supplied context differs")
    event("EXTERNAL_TRUST_AND_EXACT_CONTEXT_PASS", records=8)
    sys.path[:0] = [str(release / "replay_root/src"), str(release / "replay_root")]
    from verified_data_factory.local_paths import io_path
    from verified_data_factory.products import engineering
    from verified_data_factory.products.validation import validate_release
    original = engineering.check_source
    record_results = {m["golden"]["record_id"]: {"candidate_id": m["golden"]["candidate_id"], "status": "NOT_OBSERVED"}
                      for m in acceptance["members"]}
    def observed(golden, quality, root):
        began = time.monotonic()
        event("CHECK_SOURCE_ENTER", candidate_id=golden.candidate_id, record_id=golden.record_id)
        try:
            result = original(golden, quality, root)
        except BaseException:
            record_results[golden.record_id] = {"candidate_id": golden.candidate_id, "status": "ERROR"}
            event("CHECK_SOURCE_ERROR", candidate_id=golden.candidate_id, record_id=golden.record_id,
                  elapsed=time.monotonic() - began, traceback=traceback.format_exc())
            raise
        record_results[golden.record_id] = {"candidate_id": golden.candidate_id, "status": "PASS"}
        event("CHECK_SOURCE_EXIT", candidate_id=golden.candidate_id, record_id=golden.record_id,
              elapsed=time.monotonic() - began, status="PASS")
        return result
    engineering.check_source = observed
    with (output / "faulthandler.log").open("x", encoding="utf-8") as diagnostic:
        faulthandler.enable(file=diagnostic)
        faulthandler.dump_traceback_later(180, repeat=True, file=diagnostic)
        try:
            implementation = sys.modules[validate_release.__module__].__file__
            event("BUNDLED_VALIDATE_RELEASE_ENTER", implementation=implementation)
            result = validate_release(io_path(release),
                qualities_by_id={m["golden"]["record_id"]: m["quality"] for m in acceptance["members"]},
                justifications={m["golden"]["record_id"]: m["quality"].get("mutation_justification", "") for m in acceptance["members"]})
            payload = {"report": result.model_dump(mode="json"), "context_sha256": PINS["quality-context.json"],
                       "implementation": implementation, "scope": "new native bundled validate_release; exact pinned supplied context"}
            save(output / "bundled-validation-result.json", payload)
            event("BUNDLED_VALIDATE_RELEASE_EXIT", status=result.status, errors=len(result.errors), records=result.record_count)
            require(result.status == "VALID" and not result.errors and not result.warnings and result.record_count == 8,
                    "bundled validation did not pass cleanly")
            require(all(r["status"] == "PASS" for r in record_results.values()), "not all eight source checks observed passing")
        finally:
            faulthandler.cancel_dump_traceback_later()
            save(output / "per-record-results.json", record_results)


if __name__ == "__main__":
    main()
