"""Model-free Phase 2: recorded observations and current typed conformance."""
from __future__ import annotations

import hashlib
import json
import runpy
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from engineering_campaign import OUT, ROOT, safety, stamp, write_new
from engineering_score import digest
from package_a_evidence import (
    load_events,
    materialize,
    rebuild,
    source_tree_identity,
    validate_event,
)
from phase3_diagnostic import _reference_sql

from verified_data_factory.sandbox import load_config as load_sandbox_config
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.adversarial import independent_adversarial_tables
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.comparator import compare
from verified_data_factory.verification.models import ComparisonPolicy, ExpectedResult
from verified_data_factory.verification.mutations import MutationContext, run_mutation_checks
from verified_data_factory.verification.oracle_registry import get_oracle


def supersede() -> None:
    journal = ROOT / "scratch/funnel_experiment/evidence/events.jsonl"
    entries = materialize(load_events(journal))["entries"]
    selected = [e for e in entries if e["status"] == "ACTIVE" and not str(e["phase"]).startswith("engineering")
                and any(word in (e["evidence_id"] + " " + e["event_type"]).lower()
                        for word in ("regression", "mutation", "differential", "fuzz", "challenge", "readiness", "experiment", "gate-checklist"))]
    path = OUT / "phase2-supersession.json"
    if path.exists():
        # Resume even if interruption occurred partway through journal appends.
        ids = json.loads(path.read_text())["superseded_ids"]
        selected = [e for e in entries if e["evidence_id"] in ids]
    else:
        write_new(path, {"recorded_at": stamp(), "reason": "Comparator foundation changed; prior qualification is not current certification.",
                         "superseded_ids": [e["evidence_id"] for e in selected], "raw_artifacts_preserved": True})
    existing_ids = {e["evidence_id"] for e in entries}
    identity = source_tree_identity(ROOT)
    with journal.open("a", encoding="utf-8") as handle:
        for previous in selected:
            if "engineering-2-supersedes-" + previous["evidence_id"] in existing_ids:
                continue
            event = {**previous, "evidence_id": "engineering-2-supersedes-" + previous["evidence_id"],
                     "event_type": "comparator_foundation_supersession", "artifact_path": path.relative_to(ROOT).as_posix(),
                     "sha256": digest(path), "status": "INFORMATIONAL", "supersedes": previous["evidence_id"],
                     "superseded_by": None, "producer_script": "scripts/engineering_rejudge.py",
                     "producer_command": "python scripts/engineering_rejudge.py", "source_tree_identity": identity,
                     "created_at": stamp(), "phase": "engineering-2", "notes": "Re-adjudicate; do not edit historical observations."}
            validate_event(event)
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    rebuild(ROOT)


def recorded_candidates() -> dict[str, Any]:
    reports = {}
    for path in sorted((ROOT / "scratch/funnel-generation-experiment").glob("*/calls.jsonl")):
        ledger = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        results = []
        for number, call in enumerate(ledger, 1):
            old = call.get("verification") or {}
            execution = call.get("execution") or {}
            expected = (old.get("oracle") or {}).get("expected")
            actual = execution.get("result_data")
            previous = old.get("verdict")
            row = {"line": number, "arm": call.get("arm"), "candidate_id": (call.get("candidate") or {}).get("candidate_id"),
                   "old_verdict": previous, "new_recorded_stage_verdict": previous,
                   "business_independence": "UNPROVEN; snapshot comparison only"}
            if expected is not None and actual is not None and execution.get("status") == "SUCCEEDED":
                result = compare(ExpectedResult.model_validate(expected), [c["name"] for c in actual["columns"]],
                                 actual["rows"], ComparisonPolicy.model_validate((old.get("comparison") or {}).get("policy") or {}),
                                 column_types=[c["type"] for c in actual["columns"]])
                old_match = (old.get("comparison") or {}).get("match")
                row.update(old_comparison_match=old_match, new_comparison_match=result.match, notes=result.notes)
                if not result.match:
                    row["new_recorded_stage_verdict"] = "FAIL"
                elif old_match is False:
                    # A rescued visible match cannot establish skipped later stages.
                    row["new_recorded_stage_verdict"] = "UNPROVEN_REQUIRES_DOWNSTREAM_REPLAY"
            else:
                row["comparison"] = "NOT_APPLICABLE_EARLY_EXIT_OR_UNAVAILABLE_OBSERVATION"
            results.append(row)
        original_report = json.loads((path.parent / "report.json").read_text())
        reported_count = sum(s["calls"] for s in original_report["summaries"].values())
        reports[path.parent.name] = {"ledger_sha256": digest(path), "actual_call_rows": len(ledger),
                                   "historically_reported_count_including_reused_baselines": reported_count,
                                   "logged_attempts_without_candidate_verdict": sum(r["old_verdict"] is None for r in results),
                                   "by_arm": dict(Counter(str(c["arm"]) for c in ledger)),
                                   "verdict_changes": dict(Counter(f"{r['old_verdict']} -> {r['new_recorded_stage_verdict']}" for r in results)),
                                   "records": results}
    return reports


def evaluate(task: Any, tables: dict[str, Any], sql: str) -> dict[str, Any]:
    expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, tables)
    connection = materialize_duckdb(task.schema_, tables)
    try:
        cursor = connection.execute(sql)
        columns = [c[0] for c in cursor.description]
        types = [str(c[1]) for c in cursor.description]
        observed = [[str(v) if isinstance(v, date | datetime) else v for v in row] for row in cursor.fetchall()]
        result = compare(expected, columns, observed, column_types=types)
        return {"classification": "MATCH" if result.match else "KILLED_WRONG_ANSWER", "notes": result.notes,
                "columns": columns, "types": types}
    except Exception as exc:  # noqa: BLE001 - errors are evidence, never semantic kills.
        return {"classification": "EXECUTION_ERROR", "error": f"{type(exc).__name__}: {exc}"}
    finally:
        connection.close()


def conformance() -> list[dict[str, Any]]:
    from tests.test_logistics_funnel_v2 import LOGISTICS_V2_WINDOW_SQL
    references = _reference_sql()
    references["sql.funnel.logistics_parcel_delivery"] = LOGISTICS_V2_WINDOW_SQL
    latest = {}
    backend = DerivedTaskBackend(load_sandbox_config(ROOT / "configs/sandbox_production.yaml"))
    for template in load_builtin_registry().list():
        if template.template_id not in latest or latest[template.template_id].version < template.version:
            latest[template.template_id] = template
    results = []
    for template_id, template in sorted(latest.items()):
        task = generate_task(template, 94001)
        reference = references.get(template_id)
        if reference is None:
            results.append({"contract": template_id, "version": template.version, "classification": "MISSING_REFERENCE"})
            continue
        for label, tables in (("generated", task.tables), ("adversarial", independent_adversarial_tables(task))):
            if tables is None:
                results.append({"contract": template_id, "version": template.version, "fixture": label, "classification": "MISSING_FIXTURE"})
                continue
            result = evaluate(task, tables, reference)
            expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, tables)
            campaign = run_mutation_checks(MutationContext(task, reference, tables, expected, backend, ComparisonPolicy()), 20, 1.0)
            results.append({"contract": template_id, "version": template.version, "fixture": label,
                            "reference_sha256": hashlib.sha256(reference.encode()).hexdigest(),
                            **result, "mutation": campaign.model_dump(mode="json"),
                            "mutation_numerator": campaign.semantic_kills,
                            "mutation_denominator": campaign.semantic_kills + campaign.survived,
                            "survivor_disposition": "OPEN_COVERAGE_FINDING_FOR_PHASE_7" if campaign.survived else "NONE"})
    return results


def challenges() -> dict[str, Any]:
    old = runpy.run_path(str(ROOT / "scratch/funnel_experiment/evidence/run_phase5_private_corpus.py"))
    task = old["task"]()
    tables = independent_adversarial_tables(task)
    assert tables is not None
    originals = [{"id": query["id"], "declared_category": query["category"], **evaluate(task, tables, query["sql"])}
                 for query in old["query_catalog"]()]
    corpus = json.loads((ROOT / "scratch/funnel_experiment/evidence/phase5-private-saas-corpus.json").read_text())
    alternatives = []
    for query in old["query_catalog"]():
        if query["category"] == "qualified_correct_alternative":
            outcomes = [evaluate(task, case["tables"], query["sql"]) for case in corpus["corpus"]]
            alternatives.append({"id": query["id"], "cases": len(outcomes),
                                 "matched": sum(o["classification"] == "MATCH" for o in outcomes),
                                 "failures": [o for o in outcomes if o["classification"] != "MATCH"]})
    repair = json.loads((ROOT / "scratch/funnel_experiment/evidence/challenge-repair-private.json").read_text())
    repaired = [{"id": q["name"], **evaluate(task, q["witness"], q["sql"])} for q in repair["queries"]]
    return {"original_corpus": originals, "correct_alternative_replay": alternatives, "repaired_corpus": repaired,
            "semantic_kills_in_repair": sum(q["classification"] == "KILLED_WRONG_ANSWER" for q in repaired),
            "note": "Execution errors are separate. Corpus coverage/alternative qualification is not inferred from counts."}


def fuzz_replay() -> dict[str, Any]:
    namespace = runpy.run_path(str(ROOT / "scratch/funnel_experiment/evidence/run_phase6_saas_v2_fuzz.py"))
    from tests.test_business_tasks import SAAS_V2_CHAINED_JOIN_SQL
    from tests.test_saas_v2_differential_sql import RECURSIVE_SQL
    task = namespace["_task"]()
    threshold = json.loads((ROOT / "scratch/funnel_experiment/evidence/phase6-saas-v2-fuzz-threshold.json").read_text())
    import random
    failures = []
    checked = 0
    for seed in threshold["seeds"]:
        scheduled = [b for b in namespace["BEHAVIORS"] for _ in range(threshold["behavior_minimum_per_seed"])]
        rng = random.Random(seed)
        scheduled.extend(rng.choice(namespace["BEHAVIORS"]) for _ in range(threshold["cases_per_seed"] - len(scheduled)))
        rng.shuffle(scheduled)
        for index, behavior in enumerate(scheduled):
            tables = namespace["_case"](seed, index, behavior)
            for label, sql in (("recursive", RECURSIVE_SQL), ("join", SAAS_V2_CHAINED_JOIN_SQL)):
                result = evaluate(task, tables, sql)
                if result["classification"] != "MATCH":
                    failures.append({"seed": seed, "case": index, "sql": label, **result})
            checked += 1
    return {"cases": checked, "failures": failures,
            "scope": "Replay of old scheduled cases with typed schema/order comparison; random coverage not certified."}


def main() -> None:
    safety()
    supersede()
    report = {"created_at": stamp(), "model_calls": 0, "recorded_candidates": recorded_candidates(),
              "current_registered_semantics_conformance": conformance(), "challenge_replay": challenges(),
              "fuzz_replay": fuzz_replay(), "label": "differential verification; old snapshot judgments separated from forward semantics"}
    report["supersedes_provisional_artifact"] = "phase2-rejudgement.json"
    report["source_hashes"] = {p: digest(ROOT / p) for p in (
        "scripts/engineering_rejudge.py", "src/verified_data_factory/verification/comparator.py",
        "src/verified_data_factory/verification/models.py", "src/verified_data_factory/verification/mutations.py",
        "src/verified_data_factory/verification/business_oracles.py", "src/verified_data_factory/verification/oracle_registry.py",
        "src/verified_data_factory/task_engine/business_fixtures.py",
    )}
    path = OUT / "phase2-rejudgement-r1.json"
    write_new(path, report)
    print(json.dumps({"actual_call_rows": {k: v["actual_call_rows"] for k, v in report["recorded_candidates"].items()},
                      "verdict_changes": {k: v["verdict_changes"] for k, v in report["recorded_candidates"].items()},
                      "conformance": dict(Counter(r["classification"] for r in report["current_registered_semantics_conformance"])),
                      "repaired_semantic_kills": report["challenge_replay"]["semantic_kills_in_repair"],
                      "replayed_fuzz_cases": report["fuzz_replay"]["cases"], "fuzz_failures": len(report["fuzz_replay"]["failures"])}, indent=2))


if __name__ == "__main__":
    main()
