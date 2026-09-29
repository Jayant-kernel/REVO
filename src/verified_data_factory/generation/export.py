"""Candidate JSON/JSONL serialization (Phase 2).

Round-trippable and stable. Never carries correctness fields —
there are none on the model to leak.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .generator import candidate_to_dict
from .models import CandidateSolution

__all__ = [
    "candidate_from_dict",
    "candidate_from_json",
    "candidate_to_dict",
    "candidate_to_json",
    "read_candidates_jsonl",
    "write_candidates_jsonl",
]


def candidate_to_json(candidate: CandidateSolution) -> str:
    return json.dumps(candidate_to_dict(candidate), indent=2)


def candidate_from_dict(data: dict[str, Any]) -> CandidateSolution:
    return CandidateSolution.model_validate(data)


def candidate_from_json(text: str) -> CandidateSolution:
    return candidate_from_dict(json.loads(text.lstrip("\ufeff")))


def write_candidates_jsonl(candidates: list[CandidateSolution], path: str | Path) -> Path:
    path = Path(path)
    with path.open("w", encoding="utf-8") as fh:
        for candidate in candidates:
            fh.write(json.dumps(candidate_to_dict(candidate), sort_keys=True) + "\n")
    return path


def read_candidates_jsonl(path: str | Path) -> list[CandidateSolution]:
    candidates = []
    with Path(path).open(encoding="utf-8-sig") as fh:
        for line in fh:
            if line.strip():
                candidates.append(candidate_from_dict(json.loads(line)))
    return candidates
