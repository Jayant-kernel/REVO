"""Positioning from verified facts and the technical datasheet (§38–§39).

Positioning centers on the actual differentiator — executable
verification plus hidden/property/metamorphic/mutation testing, audit,
provenance, and reproducible releases — never on generic
"AI-generated synthetic data". The datasheet derives every value from
real product artifacts; unknown values stay UNKNOWN.
"""

from __future__ import annotations

from typing import Any

DIFFERENTIATORS: tuple[str, ...] = (
    "synthetic generation",
    "executable verification",
    "hidden testing",
    "property/metamorphic testing",
    "mutation testing",
    "dataset-level audit",
    "provenance",
    "reproducible product releases",
)

KNOWN_LIMITATIONS: tuple[str, ...] = (
    "Analytical SQL only (DuckDB dialect).",
    "No claim of model improvement without a measured experiment.",
    "No willingness-to-pay evidence until customers act.",
)


def positioning_statement(domain: str = "analytical SQL") -> str:
    """One factual positioning paragraph built from the differentiators."""
    stack = ", ".join(DIFFERENTIATORS)
    return (
        f"Execution-verified synthetic {domain} data: {stack}. "
        "Every record ships with executable proof of correctness, not "
        "just model-generated text."
    )


def technical_datasheet(
    *,
    release_manifest: dict[str, Any],
    release_metrics: dict[str, Any] | None = None,
    benchmark_id: str | None = None,
    reproducibility_level: str = "UNKNOWN",
) -> dict[str, Any]:
    """Factual datasheet derived from actual artifacts (§39)."""
    metrics = release_metrics or {}
    return {
        "domain": "analytical SQL",
        "task_families": sorted((metrics.get("family_distribution") or {}).keys()),
        "sql_dialect": "DuckDB",
        "verification_method": "independent oracles + hidden/property/metamorphic checks + mutation scoring",
        "quality_methodology": "task-quality, duplicates, diversity, coverage, difficulty, contamination, audit sampling",
        "provenance_methodology": "content-addressed lineage + dataset snapshots + reproduction manifests",
        "dataset_formats": [release_manifest.get("output_format", "UNKNOWN")],
        "schema_version": release_manifest.get("schema_version", "UNKNOWN"),
        "release_version": release_manifest.get("release_id", "UNKNOWN"),
        "record_count": release_manifest.get("record_count", "UNKNOWN"),
        "coverage": metrics.get("coverage_summary", "UNKNOWN"),
        "known_limitations": list(KNOWN_LIMITATIONS),
        "reproducibility_level": reproducibility_level,
        "benchmark_id": benchmark_id or "UNKNOWN",
    }


def datasheet_markdown(datasheet: dict[str, Any]) -> str:
    """Render the datasheet as Markdown for GTM materials."""
    lines = ["# Technical datasheet", ""]
    for key in sorted(datasheet):
        lines.append(f"- {key}: {datasheet[key]}")
    return "\n".join(lines) + "\n"
