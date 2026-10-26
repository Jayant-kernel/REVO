"""Independently validate the authoritative Phase 14 report."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REQUIRED_SECTIONS = (
    "Executive Conclusion",
    "What Changed",
    "Verified Evidence and Reproduction Commands",
    "Remaining Unproven",
    "Corrected Readiness Counts and Independence Labels",
    "Superseded Claims",
    "Regression Results and Source Identity",
    "Frozen-Run Integrity",
    "Mutation Survivors and Challenge Outcomes",
    "Fuzz Coverage and Divergences",
    "Quarantined Experiments and Version Identity",
    "Phase 13 Results and Threshold Outcomes",
    "Score Outputs and Quality Profile",
    "Needs User Review",
    "Proposed Packages B and Later",
)


def check(report_path: Path, index_path: Path) -> dict[str, Any]:
    report = report_path.read_text(encoding="utf-8")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    headings = re.findall(r"^## (.+)$", report, flags=re.MULTILINE)
    section_citations = re.findall(
        r"^## .+?\n(.*?)(?=^## |\Z)", report, flags=re.MULTILINE | re.DOTALL
    )
    citations = [
        citation
        for section in section_citations
        for citation in re.findall(r"Evidence: `([^`]+)`", section)
    ]
    cited_ids = [
        evidence_id
        for citation in citations
        for evidence_id in re.split(r"\s*,\s*", citation)
        if evidence_id
    ]
    active_ids = {
        entry["evidence_id"]
        for entry in index["entries"]
        if entry["status"] == "ACTIVE"
    }
    unknown_or_inactive = sorted(set(cited_ids) - active_ids)
    report_sections = tuple(headings)
    result = {
        "active_evidence_count": len(active_ids),
        "citation_count": len(cited_ids),
        "sections_without_citations": [
            REQUIRED_SECTIONS[index]
            for index, section in enumerate(section_citations)
            if not re.search(r"Evidence: `[^`]+`", section)
        ],
        "duplicate_citations": sorted(
            citation for citation in set(cited_ids) if cited_ids.count(citation) > 1
        ),
        "exact_required_sections": report_sections == REQUIRED_SECTIONS,
        "inactive_or_unknown_citations": unknown_or_inactive,
        "report_section_count": len(report_sections),
        "required_section_count": len(REQUIRED_SECTIONS),
    }
    result["status"] = "PASS" if (
        result["exact_required_sections"]
        and not unknown_or_inactive
        and not result["sections_without_citations"]
    ) else "FAIL"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = check(args.report, args.index)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
