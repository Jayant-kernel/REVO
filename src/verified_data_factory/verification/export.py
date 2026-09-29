"""VerificationResult JSON/JSONL serialization (Phase 4).

Stable field names, bounded evidence (diffs capped, hidden seeds only —
never fixture contents), version metadata, no secrets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import VerificationResult

__all__ = [
    "read_verifications_jsonl",
    "verification_from_dict",
    "verification_from_json",
    "verification_to_dict",
    "verification_to_json",
    "write_verifications_jsonl",
]


def verification_to_dict(result: VerificationResult) -> dict[str, Any]:
    return result.model_dump(mode="json", by_alias=True)


def verification_to_json(result: VerificationResult) -> str:
    return json.dumps(verification_to_dict(result), indent=2)


def verification_from_dict(data: dict[str, Any]) -> VerificationResult:
    return VerificationResult.model_validate(data)


def verification_from_json(text: str) -> VerificationResult:
    return verification_from_dict(json.loads(text.lstrip("\ufeff")))


def write_verifications_jsonl(results: list[VerificationResult], path: str | Path) -> Path:
    path = Path(path)
    with path.open("w", encoding="utf-8") as fh:
        for result in results:
            fh.write(json.dumps(verification_to_dict(result), sort_keys=True) + "\n")
    return path


def read_verifications_jsonl(path: str | Path) -> list[VerificationResult]:
    results = []
    with Path(path).open(encoding="utf-8-sig") as fh:
        for line in fh:
            if line.strip():
                results.append(verification_from_dict(json.loads(line)))
    return results
