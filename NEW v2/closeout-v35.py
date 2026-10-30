"""Validate current measurements, reject substituted context, preserve checklist IDs."""
from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "NEW v2")]
spec = importlib.util.spec_from_file_location("consolidation", ROOT / "NEW v2/consolidate-v35.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
from scripts import engineering_rule_measurement as rules
from scripts import engineering_discrimination_measurement as discrimination
from scripts.package_a_paused_run_guard import read_baseline
from scripts.company_generation_experiment import budget_usage, BUDGET


def context_gate(context, expected, checksum, pin):
    if checksum != pin:
        raise ValueError("separately pinned context identity differs")
    if context != expected:
        raise ValueError("context differs from exact anchored release acceptance")


def main():
    c.stable()
    inventory = c.load(c.OUT / "inventory.json")
    controls = []
    for name in ("renewal-v34-round2", "queue-v35-round2"):
        context_path = c.OUT / (name + "-quality-context.json")
        context = c.load(context_path)
        launch = c.load(c.OUT / (name + "-quality-launch.json"))
        assert c.sha(context_path) == launch["sidecar_sha256"]
        base = Path(context["package"]["base"])
        assert c.sha(base / "release/manifest.json") == launch["manifest_sha256"]
        manifest = c.load(base / "release/manifest.json")
        entry = next(e for e in manifest["files"] if e["relative_path"] == "engineering_acceptance.json")
        assert c.sha(base / "release/engineering_acceptance.json") == entry["content_hash"] == context["acceptance_sha256"]
        expected = copy.deepcopy(context)
        expected["acceptance"] = c.load(base / "release/engineering_acceptance.json")
        context_gate(context, expected, c.sha(context_path), launch["sidecar_sha256"])
        assert c.load(c.OUT / (name + "-quality.json"))["report"]["status"] == "VALID"
        for damage in ("candidate", "task", "snapshot", "role", "quality", "source"):
            bad = copy.deepcopy(context)
            member = bad["acceptance"]["members"][0]
            if damage == "candidate":
                member["golden"]["candidate_id"] += ".substituted"
            elif damage == "task":
                member["golden"]["task"]["task_id"] += ".substituted"
            elif damage == "snapshot":
                bad["acceptance"]["snapshot"]["dataset_snapshot_id"] = "sha256:" + "0" * 64
            elif damage == "role":
                bad["acceptance"]["role"] = "EVAL"
            elif damage == "quality":
                member["quality"]["verification"]["mutation_score"] = 0
            else:
                bad["acceptance_sha256"] = "0" * 64
            path = c.OUT / (name + "-negative-" + damage + ".json")
            c.save(path, bad)
            checksum = c.sha(path)
            for recomputed in (False, True):
                try:
                    context_gate(bad, expected, checksum, checksum if recomputed else launch["sidecar_sha256"])
                except ValueError as exc:
                    controls.append(dict(package=name, damage=damage, attacker_recomputed_pin=recomputed, result="REJECTED", reason=str(exc)))
                else:
                    raise AssertionError("substituted context accepted")
    metrics = {}
    for producer, filename in ((rules, "criterion-contract-rules-v35.json"), (discrimination, "criteria-discrimination-v35.json")):
        path = c.ENG / filename
        ref = dict(path=path.relative_to(ROOT).as_posix(), sha256=c.sha(path))
        c.progress("LIVE_MEASUREMENT_VALIDATE", producer=producer.PRODUCER)
        metrics[filename] = producer.validate(ROOT, ref)
        data = c.load(path)
        for damage in ("empty", "partial", "duplicate", "version", "metric", "source"):
            bad = copy.deepcopy(data)
            if damage == "empty":
                bad["population"] = []
            elif damage == "partial":
                bad["population"] = bad["population"][:-1]
            elif damage == "duplicate":
                bad["population"][1] = bad["population"][0]
            elif damage == "version":
                bad["population"][0]["contract_version"] = 999
            elif damage == "metric":
                bad["metrics"] = {k: -1 for k in bad["metrics"]}
            else:
                bad["source_hashes"]["src/verified_data_factory/verification/models.py"] = "0" * 64
            target = c.OUT / (filename.removesuffix(".json") + "-negative-" + damage + ".json")
            c.save(target, bad)
            try:
                producer.validate(ROOT, dict(path=target.relative_to(ROOT).as_posix(), sha256=c.sha(target)))
            except ValueError as exc:
                controls.append(dict(producer=producer.PRODUCER, damage=damage, result="REJECTED", reason=str(exc)))
            else:
                raise AssertionError("altered measurement accepted")
    c.save(c.OUT / "negative-controls.json", controls)
    baseline = read_baseline(ROOT / "scratch/paused-run.baseline.sha256.txt")
    actual = {p.relative_to(ROOT / "runs/premium-qualification-080").as_posix(): c.sha(p)
              for p in (ROOT / "runs/premium-qualification-080").rglob("*") if p.is_file()}
    assert actual == baseline and len(actual) == 15
    for p, digest in inventory["protected_hashes"].items():
        assert c.sha(Path(p)) == digest
    usage = budget_usage([json.loads(line) for line in BUDGET.read_text().splitlines()])
    assert usage == inventory["budget"]
    c.stable()
    old_path = c.ENG / "company-progress-checklist-v1-snapshot-4/checklist.json"
    checklist = c.load(old_path)
    checklist["version"] = "company-progress-v1-snapshot-5-delivery-v35"
    checklist["previous_snapshot"] = dict(path=old_path.relative_to(ROOT).as_posix(), sha256=c.sha(old_path))
    checklist["source"] = dict(scope="bounded v35 consolidation; no full same-source suite certificate", inventory=str(c.OUT / "inventory.json"))
    evidence = {"W02": "inventory.json", "W03": "queue-v35-round2-quality.json", "W08": "inventory.json", "W09": "partial-pool-screen.json", "W12": "summary.json", "W16": "HANDOFF.md"}
    for row in checklist["requirements"]:
        if row["id"] in evidence:
            row["evidence_paths"].append((c.OUT / evidence[row["id"]]).relative_to(ROOT).as_posix())
    checklist["separate_statuses"].update(contract_qualification="20_OF62_CURRENT;42_LATEST_QUARANTINED;140_CATEGORY_RECEIPTS",
        dataset_acceptance="NOT_ESTABLISHED_0_OF80;EIGHT_DISTINCT_DEVELOPMENT_DELIVERIES",
        measurement_readiness="FOUR_CURRENT_FULL62_MEASUREMENTS_TARGETS_UNMET;TWENTY_DUE")
    target = c.ENG / "company-progress-checklist-v1-snapshot-5"
    target.mkdir(exist_ok=False)
    c.save(target / "checklist.json", checklist)
    screen = c.load(c.OUT / "partial-pool-screen.json")
    summary = dict(status="BOUNDED_CONSOLIDATION_VERIFIED_WITH_LIMITS", delivered_representatives=8, packages=6,
        archived_receipt_freshness=dict(Counter(r["archived_receipt_live_freshness"] for r in inventory["rows"])),
        latest_qualified=20, latest_contracts=62, latest_quarantined=42, category_receipts=140,
        metrics=metrics, rule_denominators=c.load(c.ENG / "criterion-contract-rules-v35.json")["denominators"],
        discrimination_denominators=c.load(c.ENG / "criteria-discrimination-v35.json")["denominators"],
        partial_pool_gates=screen["gates"], failed_row_contracts=[r["contract_id"] for r in inventory["rows"] if r["golden_record_id"] in {f["record_id"] for f in screen["row_failures"]}],
        current_qualified_template_counts=inventory["current_qualified_template_counts"],
        qualified_template_deficit_to_four_each={f: max(0, 4-n) for f, n in inventory["current_qualified_template_counts"].items()},
        new_supplied_quality_context_replays=2, previous_supplied_quality_context_replays=1,
        historical_campaigns_regenerated=False, negative_controls_rejected=len(controls), paused_files_unchanged=15,
        budget=usage, milestone_calls_used=5, milestone_call_limit=12, new_calls_this_consolidation=0,
        program_remaining_calls=360-usage["physical_attempts"], program_remaining_seconds=14400-usage["generation_seconds"],
        checklist_summary=checklist["summary"], completed_requirement_percentage=12.5,
        score="NOT_COMPUTABLE", missing_scoring_inputs=20, full_suite="NOT_CERTIFIED_PRIOR_THREE_HOUR_TIMEOUT",
        accepted80=0, company_examples=0, human_review="PENDING", sharing="BLOCKED", utility="NOT_MEASURED")
    c.save(c.OUT / "summary.json", summary)
    c.progress("CLOSEOUT_VERIFIED", negative_controls=len(controls), full80=0, score="NOT_COMPUTABLE")


if __name__ == "__main__":
    main()
