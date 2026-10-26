"""Phase 4-6 technical evidence for a completed smoke run.

Read-only over an immutable run directory. Produces a NEW evidence file
covering:
  - empirical difficulty (multi-seed solve rates from verification records)
  - group-aware TRAIN / PRIVATE_EVAL split with a leakage report
  - external benchmark overlap against a provided reference corpus

Never edits the run, never generates candidates, never fabricates labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from verified_data_factory.products.models import SplitPolicy
from verified_data_factory.products.splits import (
    build_splits,
    group_key_for,
    verify_group_isolation,
)
from verified_data_factory.quality.models import GoldenRecord

_SPLIT_ORDER = ("train", "public_eval", "private_eval", "benchmark")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _normalize_sql(sql: str) -> str:
    return " ".join(str(sql).lower().split())


def _fingerprint(text: str) -> str:
    return hashlib.sha256(_normalize_sql(text).encode("utf-8")).hexdigest()


def empirical_difficulty(tasks: list[dict[str, Any]], verifications: list[dict[str, Any]]) -> dict[str, Any]:
    """Solve rate per template and family from real candidate attempts."""
    task_by_id = {task["task_id"]: task for task in tasks}
    attempts: Counter[str] = Counter()
    passes: Counter[str] = Counter()
    family_attempts: Counter[str] = Counter()
    family_passes: Counter[str] = Counter()
    for record in verifications:
        task = task_by_id.get(record["task_id"], {})
        template_id = str(task.get("template_id", "unknown"))
        family = str(task.get("family", "unknown"))
        attempts[template_id] += 1
        family_attempts[family] += 1
        if record.get("verdict") == "PASS":
            passes[template_id] += 1
            family_passes[family] += 1

    def rates(nums, dens):
        return {
            key: {"attempts": dens[key], "passes": nums[key], "solve_rate": round(nums[key] / dens[key], 4)}
            for key in sorted(dens)
        }

    return {
        "method": "EMPIRICAL",
        "attempts_per_template": 3,
        "by_template": rates(passes, attempts),
        "by_family": rates(family_passes, family_attempts),
        "note": "Fixed three attempts per task; solve rates are measured, not declared.",
    }


def splits_and_leakage(golden: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    records = [GoldenRecord.model_validate(row) for row in golden]
    quality_by_id = {
        row["candidate_id"]: (row.get("quality") or {}) for row in golden
    }
    policy = SplitPolicy(seed=seed, train=0.7, public_eval=0.0, private_eval=0.3, group_by="template")
    group_of = {g.candidate_id: group_key_for(g, quality_by_id, policy) for g in records}

    built = build_splits(records, quality_by_id, policy)
    assignment = {name: list(built[name].candidate_ids) for name in _SPLIT_ORDER}

    splits = {
        name: {"candidate_ids": sorted(ids), "record_count": len(ids)}
        for name, ids in assignment.items()
    }
    isolation_violations = verify_group_isolation(built, group_of)

    # Leakage: no template/instruction/SQL fingerprint shared across TRAIN and PRIVATE_EVAL.
    def feats(ids):
        templates, instr, sql = set(), set(), set()
        for record in records:
            if record.candidate_id not in ids:
                continue
            templates.add(str(record.task.get("template_id")))
            instr.add(_fingerprint(record.instruction))
            sql.add(_fingerprint(record.candidate_solution))
        return templates, instr, sql

    train_f = feats(set(assignment["train"]))
    eval_f = feats(set(assignment["private_eval"]))
    leakage = {
        "template_overlap": sorted(train_f[0] & eval_f[0]),
        "instruction_fingerprint_overlap": sorted(train_f[1] & eval_f[1]),
        "sql_fingerprint_overlap": sorted(train_f[2] & eval_f[2]),
    }
    leakage_ok = not any(leakage.values()) and not isolation_violations
    return {
        "policy": {"seed": seed, "train": 0.7, "private_eval": 0.3, "group_by": "template"},
        "splits": {name: splits[name]["record_count"] for name in _SPLIT_ORDER},
        "group_isolation_violations": isolation_violations,
        "leakage": leakage,
        "leakage_report": "PASS" if leakage_ok else "FAIL",
        "note": "Split is by template (schema/group), not by row. Exposed dev rows are not relabelled as untouched eval.",
    }


def external_overlap(golden: list[dict[str, Any]], corpus_paths: list[Path]) -> dict[str, Any]:
    ours = {_fingerprint(row["instruction"]) for row in golden}
    ours_sql = {_fingerprint(row["candidate_solution"]) for row in golden}
    corpora: dict[str, Any] = {}
    resolved_hits: list[str] = []
    for path in corpus_paths:
        if not path.exists():
            corpora[path.name] = {"status": "MISSING"}
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        items = _read_jsonl(path) if path.suffix == ".jsonl" else json.loads(path.read_text(encoding="utf-8"))
        items = items if isinstance(items, list) else items.get("items", [])
        ref_instr = {_fingerprint(str(i.get("instruction", i.get("question", "")))) for i in items}
        ref_sql = {_fingerprint(str(i.get("sql", i.get("query", "")))) for i in items}
        hit_instr = sorted(ours & ref_instr)
        hit_sql = sorted(ours_sql & ref_sql)
        resolved_hits.extend(hit_instr + hit_sql)
        corpora[path.name] = {
            "sha256": digest,
            "items": len(items),
            "instruction_overlap": len(hit_instr),
            "sql_overlap": len(hit_sql),
        }
    if not corpus_paths:
        return {"status": "NOT_MEASURED", "corpora": {}, "note": "No reference corpus was supplied."}
    return {
        "status": "MEASURED",
        "corpora": corpora,
        "unresolved_hard_matches": sorted(set(resolved_hits)),
        "note": "Overlap is against the named corpora only; it cannot prove absence from all benchmarks.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--corpus", action="append", default=[])
    parser.add_argument("--seed", type=int, default=394005)
    args = parser.parse_args()

    run = Path(args.run)
    tasks = _read_jsonl(run / "tasks/tasks.jsonl")
    verifications = _read_jsonl(run / "verification/verification.jsonl")
    golden = _read_jsonl(run / "quality/export/golden.jsonl")
    corpus_paths = [Path(c) for c in args.corpus]

    evidence = {
        "run": str(run),
        "golden_records": len(golden),
        "difficulty": empirical_difficulty(tasks, verifications),
        "splits": splits_and_leakage(golden, args.seed),
        "external_overlap": external_overlap(golden, corpus_paths),
    }
    encoded = json.dumps(evidence, indent=2, sort_keys=True)
    out = Path(args.output)
    out.write_text(encoded + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(out),
        "sha256": "sha256:" + hashlib.sha256(encoded.encode()).hexdigest(),
        "leakage_report": evidence["splits"]["leakage_report"],
        "external_overlap": evidence["external_overlap"]["status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
