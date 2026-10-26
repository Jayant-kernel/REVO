"""Generate the deterministic scheduler readiness manifest from Phase 3 checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase3_diagnostic import _contract_readiness

MANIFEST_VERSION = "1.0"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_manifest() -> dict[str, Any]:
    """Flatten the diagnostic matrix into the scheduler's stable input format."""
    readiness = _contract_readiness()
    columns = readiness["columns"]
    contracts = [
        {
            "contract_id": row["template_id"],
            "family": row["family"],
            "template_version": row["template_version"],
            **{column: row["checks"][column]["status"] for column in columns},
            "status": "FULLY_VERIFIED" if row["fully_verified"] else "NOT_READY",
        }
        for row in readiness["rows"]
    ]
    payload = {
        "manifest_version": MANIFEST_VERSION,
        "readiness_columns": columns,
        "contracts": contracts,
    }
    return {
        **payload,
        "manifest_hash": "sha256:" + hashlib.sha256(_canonical_bytes(payload)).hexdigest(),
    }


def write_manifest(path: Path) -> dict[str, Any]:
    manifest = build_manifest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="manifests/phase3-contract-readiness.json")
    args = parser.parse_args()
    manifest = write_manifest(Path(args.output))
    print(json.dumps({"manifest": str(args.output), "manifest_hash": manifest["manifest_hash"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
