"""Independently count Phase 10 readiness artifacts without generator imports."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def count(index_path: Path, matrix_path: Path) -> dict[str, Any]:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    payload = {key: value for key, value in index.items() if key != "index_hash"}
    index_hash_valid = index["index_hash"] == "sha256:" + hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    rows = matrix["rows"]
    statuses = Counter(row["status"] for row in rows)
    funnels = [row for row in rows if row["family"] == "funnel"]
    expected = [(row["contract_id"], row["contract_version"], row["status"]) for row in index["contracts"]]
    actual = [(row["contract_id"], row["contract_version"], row["status"]) for row in rows]
    return {
        "evidence_index_hash": index["index_hash"],
        "index_hash_valid": index_hash_valid,
        "matrix_references_index": matrix["evidence_index_hash"] == index["index_hash"],
        "matrix_matches_index_rows": actual == expected,
        "totals": {
            "contracts": len(rows),
            "fully_verified": statuses["FULLY_VERIFIED"],
            "quarantined": statuses["QUARANTINED"],
            "not_ready": statuses["NOT_READY"],
            "funnels": len(funnels),
            "fully_verified_funnels": sum(row["status"] == "FULLY_VERIFIED" for row in funnels),
        },
        "status": "PASS" if index_hash_valid and matrix["evidence_index_hash"] == index["index_hash"] and actual == expected else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = count(args.index, args.matrix)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
