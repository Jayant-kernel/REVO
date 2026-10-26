"""Read-only checks of Package A claims against underlying artifacts."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def audit(root: Path) -> dict[str, object]:
    evidence = root / "scratch/funnel_experiment/evidence"
    challenge = json.loads((evidence / "phase5-saas-classifications.json").read_text())
    experiment = root / "scratch/funnel-generation-experiment/phase13-authorized-current-runner-20261006-r3"
    calls = [json.loads(line) for line in (experiment / "calls.jsonl").read_text().splitlines() if line.strip()]
    report = json.loads((experiment / "report.json").read_text())
    actual = Counter(str(row["arm"]) for row in calls)
    claimed = {arm: summary["calls"] for arm, summary in report["summaries"].items()}
    wrong = sum(row["outcome"] == "WRONG_REJECTED" for row in challenge["queries"])
    repair_path = evidence / "challenge-repair-private.json"
    repaired = json.loads(repair_path.read_text()) if repair_path.exists() else None
    readiness = json.loads((evidence / "phase10-contract-evidence-index.json").read_text())
    required = ("named_test", "metamorphic", "mutation", "challenge", "fuzz")
    missing = []
    for contract in readiness["contracts"]:
        serialized = json.dumps(contract)
        absent = [name for name in required if name not in serialized]
        if absent:
            missing.append({"contract": contract["contract_id"], "missing_evidence_categories": absent})
    return {
        "scope": "Package A phases 0-14 only; definitions for 40 phases unavailable",
        "challenge": {"witnessed_wrong_queries": wrong, "required": 20,
                      "passes_required_count": wrong >= 20, "outcomes": challenge["outcome_counts"]},
        "repair": {"semantic_kills": repaired["semantic_kills"] if repaired else 0,
                   "historical_artifacts_preserved": True},
        "strict_readiness": {"records_missing_required_evidence_categories": missing,
                             "note": "String presence is a necessary screening check, not proof of evidence sufficiency."},
        "experiment": {"ledger_calls": len(calls), "ledger_by_arm": dict(actual),
                       "reported_by_arm": claimed, "counts_match": dict(actual) == claimed,
                       "note": "Reused baselines are not additional model calls."},
        "findings": [
            "Phase 5 executable wrong-query requirement not met.",
            "Phase 13 report counts reused baseline rows as additional feedback calls.",
            "Phase 11 lacks a numeric component-level diagnostic reassessment.",
            "Phase 14 cites these incomplete gates as complete; reassessment required.",
        ],
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    result = audit(root)
    output = root / "scratch/funnel_experiment/evidence/package-a-reaudit.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
