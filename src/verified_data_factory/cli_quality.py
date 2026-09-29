"""Quality CLI commands (Phase 5). Thin wrappers over quality.api.

Records file format (JSONL, one bundle per line)::

    {"task": {...}, "candidate": {...}, "execution": {...},
     "verification": {...}, "role": "TRAIN"}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from verified_data_factory.quality.config import QualityConfig
from verified_data_factory.quality.models import VerifiedRecord


def load_records(path: str | Path) -> list[VerifiedRecord]:
    from verified_data_factory.generation import candidate_from_dict
    from verified_data_factory.quality.models import VerifiedRecord
    from verified_data_factory.sandbox.models import ExecutionResult
    from verified_data_factory.task_engine import task_from_dict
    from verified_data_factory.verification import verification_from_dict

    records = []
    with open(path, encoding="utf-8-sig") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                bundle = json.loads(line)
                records.append(
                    VerifiedRecord(
                        task=task_from_dict(bundle["task"]),
                        candidate=candidate_from_dict(bundle["candidate"]),
                        execution=ExecutionResult.model_validate(bundle["execution"]),
                        verification=verification_from_dict(bundle["verification"]),
                        role=bundle.get("role", "UNKNOWN"),
                    )
                )
            except Exception as exc:
                raise SystemExit(f"{path}:{lineno}: invalid record bundle: {exc}") from exc
    return records


def _config(args: argparse.Namespace) -> QualityConfig:
    from verified_data_factory.quality import load_quality_config

    if getattr(args, "config", None):
        return load_quality_config(args.config)
    return QualityConfig()


def cmd_quality_record(args: argparse.Namespace) -> int:
    from verified_data_factory.quality import analyze_record

    records = load_records(args.input)
    out = [analyze_record(r).model_dump(mode="json") for r in records]
    _write_json(args.output, out)
    print(f"analyzed {len(out)} records")
    return 0


def cmd_quality_dataset(args: argparse.Namespace) -> int:
    from verified_data_factory.quality import analyze_dataset, export_dataset

    records = load_records(args.input)
    analysis = analyze_dataset(records, _config(args))
    by_decision: dict[str, int] = {}
    for quality in analysis.qualities:
        by_decision[quality.decision] = by_decision.get(quality.decision, 0) + 1
    print(f"records={len(records)} " + " ".join(f"{k}={v}" for k, v in sorted(by_decision.items())))
    if args.out_dir:
        by_id = {r.candidate.candidate_id: r for r in records}
        export_dataset(
            analysis.qualities,
            by_id,
            analysis.health.model_dump(mode="json"),
            [i.model_dump(mode="json") for i in analysis.audit_sample.items],
            args.out_dir,
        )
        print(f"exported -> {args.out_dir}")
    return 0


def cmd_quality_duplicates(args: argparse.Namespace) -> int:
    from verified_data_factory.quality import analyze_dataset

    analysis = analyze_dataset(load_records(args.input), _config(args))
    for group in analysis.duplicates.groups:
        print(
            f"{group.duplicate_type} {group.group_id} rep={group.representative_id} n={len(group.member_ids)}"
        )
    if not analysis.duplicates.groups:
        print("no duplicate groups")
    return 0


def cmd_quality_coverage(args: argparse.Namespace) -> int:
    from verified_data_factory.quality import analyze_dataset

    analysis = analyze_dataset(load_records(args.input), _config(args))
    print(json.dumps(analysis.coverage.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


def cmd_quality_health(args: argparse.Namespace) -> int:
    from verified_data_factory.quality import analyze_dataset

    analysis = analyze_dataset(load_records(args.input), _config(args))
    print(json.dumps(analysis.health.model_dump(mode="json"), indent=2, sort_keys=True))
    return 0


def cmd_quality_golden(args: argparse.Namespace) -> int:
    from verified_data_factory.quality import analyze_dataset

    analysis = analyze_dataset(load_records(args.input), _config(args))
    golden = [q.candidate_id for q in analysis.qualities if q.decision == "GOLDEN"]
    if args.output:
        Path(args.output).write_text("\n".join(sorted(golden)) + "\n", encoding="utf-8")
    else:
        for candidate_id in sorted(golden):
            print(candidate_id)
    print(f"golden={len(golden)}/{len(analysis.qualities)}", file=sys.stderr)
    return 0


def cmd_quality_audit(args: argparse.Namespace) -> int:
    from verified_data_factory.quality import analyze_dataset, record_audit_result

    analysis = analyze_dataset(load_records(args.input), _config(args))
    if args.record_id:
        updated = record_audit_result(
            analysis.audit_sample, args.record_id, args.result, note=args.note or ""
        )
        payload = [i.model_dump(mode="json") for i in updated.items]
    else:
        payload = [i.model_dump(mode="json") for i in analysis.audit_sample.items]
    _write_json(args.output, payload)
    print(f"audit items={len(payload)}")
    return 0


def _write_json(output: str | None, payload: object) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, default=str)
    if output:
        Path(output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def register_quality_commands(subparsers: argparse._SubParsersAction[Any]) -> None:
    """Attach `factory quality ...` to the root parser (called by cli.py)."""
    quality = subparsers.add_parser("quality", help="Dataset Quality & Audit commands")
    qsub = quality.add_subparsers(dest="quality_command", required=True)

    def _common(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--input", required=True, help="records JSONL file")
        parser.add_argument("--config", default=None, help="quality YAML config")

    p_record = qsub.add_parser("record", help="Per-record quality analysis")
    _common(p_record)
    p_record.add_argument("--output", default=None)
    p_record.set_defaults(func=cmd_quality_record)

    p_dataset = qsub.add_parser("dataset", help="Full analysis + optional export")
    _common(p_dataset)
    p_dataset.add_argument("--out-dir", default=None)
    p_dataset.set_defaults(func=cmd_quality_dataset)

    p_dup = qsub.add_parser("duplicates", help="Duplicate groups")
    _common(p_dup)
    p_dup.set_defaults(func=cmd_quality_duplicates)

    p_cov = qsub.add_parser("coverage", help="Coverage report")
    _common(p_cov)
    p_cov.set_defaults(func=cmd_quality_coverage)

    p_health = qsub.add_parser("health", help="Dataset health report")
    _common(p_health)
    p_health.set_defaults(func=cmd_quality_health)

    p_golden = qsub.add_parser("golden", help="Golden candidate ids")
    _common(p_golden)
    p_golden.add_argument("--output", default=None)
    p_golden.set_defaults(func=cmd_quality_golden)

    p_audit = qsub.add_parser("audit", help="Audit sample (or record one result)")
    _common(p_audit)
    p_audit.add_argument("--output", default=None)
    p_audit.add_argument("--record-id", default=None)
    p_audit.add_argument("--result", default=None, choices=["PASS", "FAIL", "UNCLEAR"])
    p_audit.add_argument("--note", default="")
    p_audit.set_defaults(func=cmd_quality_audit)
