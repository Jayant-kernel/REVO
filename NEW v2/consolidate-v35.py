"""Read-only consolidation of six anchored deliveries; new outputs only."""
import argparse
from collections import Counter
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "scratch/company_evaluation/record-delivery-v2/consolidated-v35"
ENG = ROOT / "scratch/funnel_experiment/engineering"
REVIEWER = ROOT / "scratch/company_evaluation/record-delivery-v2/reviewer"
sys.path.insert(0, str(REVIEWER))
from validate_bound_release_windows import check, io_path, sha


def load(path):
    return json.loads(io_path(path).read_bytes())


def save(path, value):
    with io_path(path).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")


def progress(phase, **fields):
    print(json.dumps(dict(phase=phase, pid=os.getpid(), at=time.time(), **fields)), flush=True)


def packages():
    old = load(ROOT / "scratch/company_evaluation/record-delivery-v2/inventory/context-v32/archive-checkpoint.json")
    rows = [dict(name=m["version"], base=m["durable"], manifest=m["manifest_sha256"], anchor=m["anchor_sha256"]) for m in old]
    for name, container, delivery, pin in (
        ("renewal-v34", "runtime-v34-002", "renewal-delivery", "renewal-durable-origin.json"),
        ("queue-v35", "queue-v35", "delivery", "durable-origin.json"),
    ):
        base = ROOT / "artifacts/internal-deliveries/v32" / container
        pins = load(base / pin)
        rows.append(dict(name=name, base=str(base / delivery), manifest=pins["manifest_sha256"], anchor=pins["anchor_sha256"]))
    return rows


def stable():
    frozen = load(ENG / "qualified-receipts-v35/freeze.json")
    for relative, expected in frozen["hashes"].items():
        assert sha(ROOT / relative) == expected, relative
    return frozen


def inventory():
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]
    from scripts.company_generation_experiment import BUDGET, budget_usage
    from scripts.engineering_campaign import safety
    from verified_data_factory.quality.models import GoldenRecord, RecordQuality
    from verified_data_factory.products.isolation import isolation_keys, schema_role_fingerprint
    from verified_data_factory.quality.duplicate_detection import detect_duplicates
    from verified_data_factory.quality.contamination import analyze_contamination
    from verified_data_factory.quality.config import load_quality_config
    from verified_data_factory.quality.premium_candidate import assess_premium_candidate
    from verified_data_factory.quality.coverage import detect_constructs, FAMILIES
    from verified_data_factory.verification.readiness import authoritative_records
    safety()
    stable()
    OUT.mkdir(exist_ok=False)
    before = {str(p): sha(p) for p in (BUDGET, ENG / "company-model-role-registry.json")}
    current = {(r["contract_id"], r["contract_version"]): r for r in authoritative_records(ROOT)}
    registry = load(ENG / "company-model-role-registry.json")
    rows, members = [], []
    for meta in packages():
        progress("CHECK_ANCHORED_PACKAGE", package=meta["name"])
        base = Path(meta["base"])
        check(base / "release", meta["manifest"], base / "packet", base / "anchor.json", meta["anchor"])
        payload = load(base / "release/engineering_acceptance.json")
        packet = load(base / "packet/membership.json")
        by_id = {m["golden"]["record_id"]: m for m in packet["members"]}
        bindings = load(base / "packet/original-artifact-bindings.json")
        for relative, digest in bindings.items():
            assert sha(ROOT / relative) == digest, relative
        for m in payload["members"]:
            g, q = m["golden"], m["quality"]
            assert by_id[g["record_id"]]["golden"] == g
            golden = GoldenRecord.model_validate(g)
            assert payload["role"] == g["dataset_role"] == q["role"] == "TRAIN"
            keys = isolation_keys(golden)
            assert all(registry.get(k) == "TRAIN" for k in keys)
            pair = (g["task"]["template_id"], g["task"]["template_version"])
            assert pair in current
            calls = []
            for relative in bindings:
                if not relative.endswith("/generation.json"):
                    continue
                generation = load(ROOT / relative)
                candidate = generation.get("candidate_solution") or generation
                if candidate.get("candidate_id") != g["candidate_id"]:
                    continue
                assert candidate["candidate_sql"] == g["candidate_solution"]
                assert candidate["task_id"] == g["task"]["task_id"]
                parent = str(Path(relative).parent).replace("\\", "/")
                calls.append(dict(generation=relative, request=parent + "/request.json", response=parent + "/http-response.json",
                                  request_sha256=bindings[parent + "/request.json"], response_sha256=bindings[parent + "/http-response.json"]))
            assert calls, g["candidate_id"]
            embedded = q["engineering_record"]
            closure = {}
            for ref in embedded["evidence"].values():
                receipt = load(base / "release/replay_root" / ref["path"])
                closure.update(receipt["source_hashes"])
            stale = [p for p, digest in closure.items() if sha(ROOT / p) != digest]
            rows.append(dict(package=meta["name"], durable_location=str(base), golden_record_id=g["record_id"],
                content_id=by_id[g["record_id"]]["content_id"], candidate_id=g["candidate_id"], task_id=g["task"]["task_id"],
                contract_id=pair[0], contract_version=pair[1], family=q["family"], snapshot_id=payload["snapshot"]["dataset_snapshot_id"],
                physical_bindings=calls, instruction=g["instruction"], schema_role=schema_role_fingerprint(g["schema"]),
                domain=g["task"].get("generation_metadata", {}).get("config", {}).get("domain"),
                constructs=sorted(detect_constructs(g["candidate_solution"])), fixture_edges=g["fixture"].get("edge_cases", []),
                archived_verification=q["verification"], exposure="TRAIN_EXPOSED_DEVELOPMENT", role="TRAIN",
                current_catalog_qualification="CURRENT_V35", archived_receipt_live_freshness="STALE" if stale else "SOURCE_CURRENT",
                changed_archived_source_dependencies=stale, candidate_current_reverification="NOT_RUN_DURING_CONSOLIDATION",
                quality_replay="historical standalone; see supplied-context replay reports for exact gates",
                historical_quality_flags=q["contamination_flags"], lineage=str(base / "packet/lineage.json")))
            members.append(m)
        progress("PACKAGE_INTEGRITY_AND_ORIGIN_PASS", package=meta["name"], records=len(payload["members"]))
    assert len(rows) == len({r["golden_record_id"] for r in rows}) == len({r["content_id"] for r in rows}) == len({r["task_id"] for r in rows}) == 8
    goldens = [m["golden"] for m in members]
    golden_path = OUT / "combined-goldens.jsonl"
    with golden_path.open("x", encoding="utf-8", newline="\n") as handle:
        for g in goldens:
            handle.write(json.dumps(g, sort_keys=True) + "\n")
    qualities = [RecordQuality.model_validate(m["quality"]) for m in members]
    tasks = {g["candidate_id"]: json.dumps(g["task"], sort_keys=True) for g in goldens}
    sql = {g["candidate_id"]: g["candidate_solution"] for g in goldens}
    schemas = {g["candidate_id"]: g["schema"] for g in goldens}
    counts = {g["candidate_id"]: json.dumps(g["fixture"].get("tables", {}), sort_keys=True) for g in goldens}
    duplicate = detect_duplicates(qualities, sql, tasks, schemas, counts)
    flags, overlap = analyze_contamination(qualities, tasks, sql, load_quality_config(ROOT / "configs/quality_premium_93.yaml"))
    screen = assess_premium_candidate(golden_path)
    save(OUT / "partial-pool-screen.json", screen)
    save(OUT / "combined-overlap.json", dict(duplicates=duplicate.model_dump(mode="json"), overlap=overlap.model_dump(mode="json"),
        flags={k: [f.model_dump(mode="json") for f in fs] for k, fs in flags.items()},
        role_conflicts=[], scope="eight selected TRAIN records; fingerprint screens, not semantic novelty proof"))
    for p, digest in before.items():
        assert sha(Path(p)) == digest
    usage = budget_usage([json.loads(line) for line in BUDGET.read_text().splitlines()])
    assert usage["physical_attempts"] == 33 and not usage["unfinished_attempts"]
    stable()
    save(OUT / "inventory.json", dict(distinct_representatives=8, durable_packages=6, rows=rows, packages=packages(), budget=usage,
        protected_hashes=before, current_catalog_qualified=20, accepted80=0, company_examples=0, human_review="PENDING", sharing="BLOCKED",
        schema_roles=len({r["schema_role"] for r in rows}), family_counts=dict(Counter(r["family"] for r in rows)),
        current_qualified_template_counts={f: sum(1 for r in current.values() if r.get("family") == f) for f in FAMILIES},
        score="NOT_COMPUTABLE", source_freeze_stable=True))
    progress("CONSOLIDATED_EIGHT", gates_pass=screen["automated_pre_review_gates_pass"], budget=usage)


def quality_child(work, output):
    sys.path[:0] = [str(work / "release/replay_root/src"), str(work / "release/replay_root")]
    from verified_data_factory.products.validation import validate_release
    acceptance = load(work / "release/engineering_acceptance.json")
    members = acceptance["members"]
    result = validate_release(io_path(work / "release"), qualities_by_id={m["golden"]["record_id"]: m["quality"] for m in members},
        justifications={m["golden"]["record_id"]: m["quality"].get("mutation_justification", "") for m in members})
    save(output, dict(report=result.model_dump(mode="json"), implementation=sys.modules["verified_data_factory.products.validation"].__file__,
        scope="bundled validator with exact anchored acceptance qualities; historical campaigns not renewed; no full-suite claim"))
    assert result.status == "VALID" and not result.errors


def quality(round_name=""):
    stable()
    for meta in packages()[-2:]:
        name, base = meta["name"] + round_name, Path(meta["base"])
        result_path = OUT / (name + "-quality.json")
        if result_path.exists():
            assert load(result_path)["report"]["status"] == "VALID"
            continue
        progress("BOUND_QUALITY_WORKCLONE", package=name)
        check(base / "release", meta["manifest"], base / "packet", base / "anchor.json", meta["anchor"])
        sidecar = dict(package=meta, acceptance=load(base / "release/engineering_acceptance.json"), acceptance_sha256=sha(base / "release/engineering_acceptance.json"))
        sidecar_path = OUT / (name + "-quality-context.json")
        save(sidecar_path, sidecar)
        work = Path(r"C:\Users\jayan\AppData\Local\Temp\opencode") / ("qc35-" + name)
        assert work.parent.is_dir()
        work.mkdir(exist_ok=False)
        shutil.copytree(io_path(base / "release"), io_path(work / "release"))
        start = time.monotonic()
        command = [sys.executable, "-B", str(Path(__file__).resolve()), "quality-child", "--work", str(work), "--output", str(result_path)]
        with (OUT / (name + "-quality.log")).open("x", encoding="utf-8") as log:
            child = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            save(OUT / (name + "-quality-launch.json"), dict(pid=child.pid, command=command, started_at=time.time(), timeout_seconds=1200,
                sidecar_sha256=sha(sidecar_path), manifest_sha256=meta["manifest"], anchor_sha256=meta["anchor"]))
            try:
                code = child.wait(timeout=1200)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                raise
        save(OUT / (name + "-quality-terminal.json"), dict(returncode=code, elapsed_seconds=time.monotonic()-start))
        assert code == 0, "see retained quality log"
        assert sha(base / "release/engineering_acceptance.json") == sidecar["acceptance_sha256"]
        assert sha(base / "release/manifest.json") == meta["manifest"]
        progress("BOUND_QUALITY_VALID", package=name, report=load(result_path)["report"])
    stable()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inventory", "quality", "quality-round2", "quality-child"))
    parser.add_argument("--work", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.action == "quality-child":
        quality_child(args.work, args.output)
    elif args.action == "quality-round2":
        quality("-round2")
    else:
        globals()[args.action]()
