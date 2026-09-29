"""Reverify the 67 Q5 Golden candidates with the remediated pipeline.

Historical artifacts remain untouched. Results are checkpointed under a new
run directory so the process is safe to resume.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.provenance import build_bundle, export_provenance_bundle
from verified_data_factory.quality import analyze_dataset, export_dataset, load_quality_config
from verified_data_factory.quality.models import GoldenRecord, VerifiedRecord
from verified_data_factory.sandbox.models import ExecutionResult
from verified_data_factory.task_engine.models import TaskInstance
from verified_data_factory.verification import (
    VerificationConfig,
    verification_from_dict,
    verify_candidate,
)

SOURCE = Path("runs/targeted-qualification-005")
OUT = Path("runs/controlled-requalification-002")
CACHE = Path("runs/controlled-requalification-001/verification/verification.jsonl")
DISALLOWED_TEMPLATE_VERSIONS = {("sql.windows.ranked", 1)}


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
        handle.flush()


def write_state(**payload: object) -> None:
    path = OUT / "run-state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    prior_golden = [
        GoldenRecord.model_validate(row)
        for row in read_jsonl(SOURCE / "quality/export/golden.jsonl")
    ]
    prior_golden = [
        record
        for record in prior_golden
        if (
            str(record.task.get("template_id", "")),
            int(record.task.get("template_version", 0)),
        )
        not in DISALLOWED_TEMPLATE_VERSIONS
    ]
    wanted = {record.candidate_id for record in prior_golden}
    triples = {
        row["candidate"]["candidate_id"]: row
        for row in read_jsonl(SOURCE / "execution/triples.jsonl")
        if row["candidate"]["candidate_id"] in wanted
    }
    if set(triples) != wanted:
        raise RuntimeError(f"missing source triples: {sorted(wanted - set(triples))}")

    verification_path = OUT / "verification/verification.jsonl"
    if not verification_path.exists() and CACHE.exists():
        for row in read_jsonl(CACHE):
            if row.get("candidate_id") in wanted:
                append_jsonl(verification_path, row)
    existing = {
        row["candidate_id"]: row
        for row in read_jsonl(verification_path)
    } if verification_path.exists() else {}
    ordered_ids = sorted(wanted)
    for index, candidate_id in enumerate(ordered_ids, 1):
        if candidate_id in existing:
            continue
        triple = triples[candidate_id]
        task = TaskInstance.model_validate(triple["task"])
        candidate = CandidateSolution.model_validate(triple["candidate"])
        execution = ExecutionResult.model_validate(triple["execution"])
        result = verify_candidate(task, candidate, execution)
        append_jsonl(verification_path, result.model_dump(mode="json"))
        existing[candidate_id] = result.model_dump(mode="json")
        write_state(status="VERIFYING", completed=index, total=len(ordered_ids))

    records: list[VerifiedRecord] = []
    for candidate_id in ordered_ids:
        triple = triples[candidate_id]
        records.append(
            VerifiedRecord(
                task=TaskInstance.model_validate(triple["task"]),
                candidate=CandidateSolution.model_validate(triple["candidate"]),
                execution=ExecutionResult.model_validate(triple["execution"]),
                verification=verification_from_dict(existing[candidate_id]),
                role="TRAIN",
            )
        )

    quality_config = load_quality_config("configs/quality_example.yaml")
    analysis = analyze_dataset(records, quality_config)
    export_dir = OUT / "quality/export"
    export_dataset(
        analysis.qualities,
        {record.candidate.candidate_id: record for record in records},
        analysis.health.model_dump(mode="json"),
        [item.model_dump(mode="json") for item in analysis.audit_sample.items],
        export_dir,
    )
    (OUT / "quality/qualities.json").write_text(
        json.dumps([q.model_dump(mode="json") for q in analysis.qualities], indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    golden = [
        GoldenRecord.model_validate(row) for row in read_jsonl(export_dir / "golden.jsonl")
    ]
    bundle = build_bundle(
        records,
        analysis.qualities,
        golden,
        analysis.audit_sample,
        {**quality_config.model_dump(mode="json"), "quality_engine_version": "1.0"},
        VerificationConfig().model_dump(mode="json"),
        "0.8.0",
        "controlled-requalification-002",
        repo_root=".",
    )
    export_provenance_bundle(
        OUT / "provenance/bundle",
        bundle["manifest"],
        bundle["reproduction"].model_dump(mode="json"),
        bundle["snapshot"],
        list(bundle["nodes"].values()),
        bundle["edges"],
        bundle["activities"],
        bundle["artifacts"],
        bundle["golden"],
        bundle["reproducibility"],
        bundle["completeness"],
        bundle["artifact_payloads"],
    )
    golden_count = len(golden)
    status = "QUALIFIED" if 30 <= golden_count <= 80 else "THRESHOLD_NOT_MET"
    write_state(
        status=status,
        source_candidates=len(ordered_ids),
        golden=golden_count,
        audit_required=sum(q.decision == "AUDIT_REQUIRED" for q in analysis.qualities),
        excluded=sum(q.decision == "EXCLUDED" for q in analysis.qualities),
        minimum=30,
        maximum=80,
    )
    print(json.dumps(json.loads((OUT / "run-state.json").read_text()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
