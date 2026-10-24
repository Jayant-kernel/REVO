"""Freeze the small reviewer layer and verify original evidence stayed unchanged."""
import hashlib
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PREVIEW = Path(__file__).resolve().parents[1]
DEST = ROOT / "artifacts/internal-previews/development-review-v37-001"
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
spec = importlib.util.spec_from_file_location("delivery37_final_guard", ROOT / "scratch/company_evaluation/record-delivery-v3/runtime/delivery37/operate.py")
assert spec and spec.loader
op = importlib.util.module_from_spec(spec)
spec.loader.exec_module(op)


def save(path, value):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    baseline = op.d.load(PREVIEW / "audit/baseline.json")
    frozen = op.check()
    package = op.d.DURABLE / "original8"
    assert op.d.trust.inventory(package) == op.d.load(op.HERE / "durable-inventory.json")
    assert op.d.usage() == baseline["budget"]
    assert op.digest(op.d.QUAL / "freeze.json") == baseline["source_freeze_sha256"]
    # Light source and evidence equality verification, not a new qualification run.
    index = op.d.load(PREVIEW / "examples/index.json")["examples"]
    members = op.d.load(package / "packet/membership.json")["members"]
    evidence_index = op.d.load(PREVIEW / "review/evidence-index.json")
    source_refs = 0
    for entry in index:
        example = op.d.load(PREVIEW / "examples" / entry["fixture"])
        member = next(m for m in members if m["candidate_id"] == example["candidate_id"])
        golden = member["golden"]
        assert example["sql"] == golden["candidate_solution"]
        assert example["schema"] == golden["task"]["schema"]
        assert example["tables"] == golden["task"]["tables"]
        row = int(entry["example_id"]) - 1
        expected = op.d.load(op.POOL / f"{row:03d}-execution.json")["result_data"]
        assert example["expected"] == expected
        for ref in example["source_bindings"].values():
            assert op.digest(ROOT / ref["path"]) == ref["sha256"]
            source_refs += 1
    # Verify every explicitly indexed source reference, including relative Temp links.
    def walk(value):
        nonlocal source_refs
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
                assert op.digest(ROOT / value["path"]) == value["sha256"], value["path"]
                source_refs += 1
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(evidence_index)
    copied = op.d.load(PREVIEW / "audit/fresh-copy.json")
    for name in ("replay.py", "native_worker.py", "windows_job.py", "test_replay.py"):
        assert sha(PREVIEW / "replay" / name) == copied["files"]["replay/" + name]
    integration = op.d.load(PREVIEW / "audit/integration-result.json")
    assert integration["status"] == "PASS" and integration["illustrative"] == integration["authoritative"] == 8
    report = op.d.load(PREVIEW / "audit/native-bundled-validation-result.json")["report"]
    assert report["status"] == "VALID" and not report["errors"] and not report["warnings"]
    # Archive reviewer material, not coordinator executors or raw generation logs.
    assert not DEST.exists()
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.mkdir()
    for name in ("examples", "replay", "review"):
        shutil.copytree(PREVIEW / name, DEST / name, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(PREVIEW / "START-HERE.md", DEST / "START-HERE.md")
    (DEST / "audit").mkdir()
    audit_files = ["baseline.json", "INTERNAL-REVIEW.md", "REVIEW-CLOSEOUT.md", "integration-result.json", "finalization-correction.md",
                   "illustrative-results.json", "illustrative-launch.json", "illustrative-terminal.json",
                   "focused-launch.json", "focused-terminal.json", "focused.stderr.log",
                   "native-launch.json", "native-terminal.json", "native-bundled-validation-result.json",
                   "native-per-record-results.json", "native-identity.json", "native-worker-events.jsonl",
                   "native-launch.json", "native-terminal.json", "check-inputs-launch.json", "check-inputs-terminal.json"]
    for name in sorted(set(audit_files)):
        shutil.copyfile(PREVIEW / "audit" / name, DEST / "audit" / name)
    broken_links = []
    for path in DEST.rglob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" not in target and not target.startswith("#"):
                if not (path.parent / target.split("#")[0]).exists():
                    broken_links.append([str(path.relative_to(DEST)), target])
    assert not broken_links, broken_links
    manifest = {p.relative_to(DEST).as_posix(): {"sha256": sha(p), "bytes": p.stat().st_size}
                for p in DEST.rglob("*") if p.is_file()}
    save(DEST / "REVIEWER-MANIFEST.json", {"scope": "DEVELOPMENT_REVIEW_PREVIEW_INTERNAL_ONLY",
         "members": manifest, "dependency_manifest_sha256": baseline["manifest_sha256"],
         "manifest_excludes_itself": True})
    total_bytes = sum(p.stat().st_size for p in DEST.rglob("*") if p.is_file())
    layer_files = len(manifest) + 1
    save(PREVIEW / "audit/FINAL-RESULT.json", {
        "status": "DEVELOPMENT_REVIEW_PREVIEW_COMPLETE", "preview_tasks_completed": 8, "preview_tasks_total": 8,
        "preview_tasks": {f"P{n:02d}": "COMPLETE" for n in range(1, 9)},
        "artifact": str(DEST.relative_to(ROOT)), "artifact_manifest_sha256": sha(DEST / "REVIEWER-MANIFEST.json"),
        "reviewer_layer_files": layer_files, "reviewer_layer_bytes": total_bytes,
        "dependency_package_files": baseline["package_files"], "dependency_package_bytes": baseline["package_bytes"],
        "dependency_release_declared_files": baseline["declared_release_files"],
        "dependency_manifest_sha256": baseline["manifest_sha256"], "source_qualification_current": True,
        "source_bound_inputs": len(frozen["hashes"]), "original_packages_unchanged": True,
        "source_references_checked": source_refs, "markdown_links_ok": True, "tested_code_unchanged": True,
        "records_verified": 8, "illustrative_replayed": 8, "authoritative_replayed": 8,
        "authoritative_report": report, "original_completed": 2, "original_total": 16, "original_percent": 12.5,
        "budget": op.d.usage(), "new_generation_calls": 0, "accepted80": 0, "company_showcase_accepted": 0,
        "human_review": "PENDING", "external_sharing": "BLOCKED", "utility": "NOT_MEASURED",
        "strict_certificate": False, "historical_native_incidents": "UNRESOLVED",
        "review": "PASS; prior Worker A authorship/access disclosed, not blind/human",
        "findings_fixed": ["M01 renewal navigation label now describes coverage for each eligible episode"],
        "minor_deferred": ["optional suite Temp evidence not bundled/durable; primary profile evidence remains package/checkout referenced",
                            "no slim authoritative closure or non-Windows portability proved"],
        "post_review_adjustment": "START-HERE clarified copying reviewer layer before writing results and added closeout navigation; no executable/SQL/evidence change"})
    print(json.dumps({"status": "COMPLETE", "files": layer_files, "bytes": total_bytes,
                      "manifest_sha256": sha(DEST / "REVIEWER-MANIFEST.json")}, indent=2))


if __name__ == "__main__":
    main()
