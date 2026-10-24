"""Independent checks on comparator-only replay and corrected call accounting."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "scratch/funnel_experiment/engineering/phase2-rejudgement-r1.json"


def test_rejudgement_covers_every_logged_candidate_without_rewriting_ledgers():
    report = json.loads(REPORT.read_text())
    assert report["model_calls"] == 0
    paths = list((ROOT / "scratch/funnel-generation-experiment").glob("*/calls.jsonl"))
    assert len(report["recorded_candidates"]) == len(paths)
    for path in paths:
        measured = report["recorded_candidates"][path.parent.name]
        ledger = [json.loads(line) for line in path.read_text().splitlines() if line]
        assert measured["actual_call_rows"] == len(ledger)
        assert len(measured["records"]) == len(ledger)
        assert measured["ledger_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert sum(measured["by_arm"].values()) == len(ledger)
        assert sum(measured["verdict_changes"].values()) == len(ledger)
    assert report["recorded_candidates"]["phase13-authorized-current-runner-20261006-r3"]["actual_call_rows"] == 36


def test_replay_reports_real_schema_and_mutation_accounting():
    report = json.loads(REPORT.read_text())
    for row in report["current_registered_semantics_conformance"]:
        assert row["classification"] == "MATCH", row
        assert len(row["columns"]) == len(row["types"]) > 0
        mutation = row["mutation"]
        assert mutation["caught"] == mutation["semantic_kills"]
        assert mutation["run"] == mutation["semantic_kills"] + mutation["survived"] + mutation["invalid"] + mutation["inconclusive"]
        assert row["mutation_numerator"] == mutation["semantic_kills"]
        assert row["mutation_denominator"] == mutation["semantic_kills"] + mutation["survived"]
        if mutation["survived"]:
            assert row["survivor_disposition"] == "OPEN_COVERAGE_FINDING_FOR_PHASE_7"
    assert report["challenge_replay"]["semantic_kills_in_repair"] == 22
    assert all(a["cases"] == a["matched"] == 41 for a in report["challenge_replay"]["correct_alternative_replay"])
    assert report["fuzz_replay"]["cases"] == 900
    assert report["fuzz_replay"]["failures"] == []


def test_replay_receipt_is_bound_to_its_certification_tree():
    report = json.loads(REPORT.read_text())
    launch = ROOT / "scratch/funnel_experiment/engineering/phase2-launch.json"
    # Once certified, compare to that launch tree, not to later phase sources.
    manifest = json.loads(launch.read_text())["identity"]["per_file_manifest"] if launch.exists() else None
    for relative, expected in report["source_hashes"].items():
        observed = manifest[relative] if manifest is not None else hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        assert observed == expected


def test_old_comparator_dependent_certifications_are_superseded():
    index = json.loads((ROOT / "scratch/funnel_experiment/evidence/index.json").read_text())
    statuses = {entry["evidence_id"]: entry["status"] for entry in index["entries"]}
    supersession = json.loads((ROOT / "scratch/funnel_experiment/engineering/phase2-supersession.json").read_text())
    assert supersession["superseded_ids"]
    assert all(statuses[evidence] == "SUPERSEDED" for evidence in supersession["superseded_ids"])
