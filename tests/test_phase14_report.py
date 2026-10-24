from __future__ import annotations

import json
from pathlib import Path

from scripts.package_a_phase14_count import REQUIRED_SECTIONS, check


def test_phase14_report_check_requires_exact_sections_and_active_citations(tmp_path: Path) -> None:
    report_path = tmp_path / "report.md"
    index_path = tmp_path / "index.json"
    report_path.write_text(
        "# Phase 14\n\n"
        + "\n\n".join(
            f"## {section}\n\nEvidence: `evidence-{position}`"
            for position, section in enumerate(REQUIRED_SECTIONS, start=1)
        )
        + "\n",
        encoding="utf-8",
    )
    index_path.write_text(
        json.dumps(
            {
                "entries": [
                    {"evidence_id": f"evidence-{position}", "status": "ACTIVE"}
                    for position in range(1, len(REQUIRED_SECTIONS) + 1)
                ]
            }
        ),
        encoding="utf-8",
    )

    result = check(report_path, index_path)

    assert result["status"] == "PASS"
    assert result["report_section_count"] == 15


def test_phase14_report_check_rejects_inactive_citation(tmp_path: Path) -> None:
    report_path = tmp_path / "report.md"
    index_path = tmp_path / "index.json"
    report_path.write_text(
        "# Phase 14\n\n"
        + "\n\n".join(
            f"## {section}\n\nEvidence: `evidence-{position}`"
            for position, section in enumerate(REQUIRED_SECTIONS, start=1)
        )
        + "\n",
        encoding="utf-8",
    )
    index_path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "evidence_id": f"evidence-{position}",
                        "status": "INFORMATIONAL" if position == 1 else "ACTIVE",
                    }
                    for position in range(1, len(REQUIRED_SECTIONS) + 1)
                ]
            }
        ),
        encoding="utf-8",
    )

    result = check(report_path, index_path)

    assert result["status"] == "FAIL"
    assert result["inactive_or_unknown_citations"] == ["evidence-1"]
