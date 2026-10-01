"""Read-only checks for the frozen 80-row pre-review composition target.

These are measurable *screens*, not a commercial readiness score or proof of
semantic novelty, external cleanliness, human review, or utility.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from verified_data_factory.task_engine.validation import RELEASE_EDGE_CASES

from .coverage import FAMILIES, SQL_CONSTRUCTS, detect_constructs
from .duplicate_detection import normalize_sql, schema_fingerprint
from .export import build_golden_record_id
from .models import GoldenRecord


def _gate(actual: Any, target: Any, passed: bool) -> dict[str, Any]:
    return {"actual": actual, "target": target, "passed": passed}


def assess_premium_candidate(golden_jsonl: str | Path) -> dict[str, Any]:
    """Assess a selected Golden JSONL without modifying it or starting a run."""
    source = Path(golden_jsonl)
    rows = [
        json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not rows:
        raise ValueError("premium candidate contains no Golden rows")

    families: Counter[str] = Counter()
    schemas: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    instructions: Counter[str] = Counter()
    sql_shapes: Counter[str] = Counter()
    task_ids: Counter[str] = Counter()
    record_ids: Counter[str] = Counter()
    candidate_ids: Counter[str] = Counter()
    templates_by_family: dict[str, set[str]] = defaultdict(set)
    constructs: set[str] = set()
    edges: set[str] = set()
    row_failures: list[dict[str, str]] = []
    flagged_rows: set[str] = set()
    excluded_mutants: list[dict[str, Any]] = []
    sibling_overlap_flags: set[str] = set()
    semantic_groups: Counter[str] = Counter()
    structural_groups: Counter[str] = Counter()

    for raw in rows:
        row = GoldenRecord.model_validate(raw)
        record_id = row.record_id
        bound_id = build_golden_record_id(
            task=row.task,
            instruction=row.instruction,
            schema=row.schema_,
            candidate_solution=row.candidate_solution,
            record_schema_version=row.record_schema_version,
        )
        if record_id != bound_id:
            row_failures.append({"record_id": record_id, "reason": "content identity mismatch"})

        family = str(row.quality.get("family", row.task.get("family", "")))
        families[family] += 1
        templates_by_family[family].add(str(row.task.get("template_id", "")))
        schemas[schema_fingerprint(row.schema_)] += 1
        domain = row.task.get("generation_metadata", {}).get("config", {}).get("domain")
        if isinstance(domain, str) and domain.strip():
            domains[domain.strip()] += 1
        instructions[" ".join(row.instruction.casefold().split())] += 1
        sql_shapes[normalize_sql(row.candidate_solution)] += 1
        task_ids[str(row.task.get("task_id", ""))] += 1
        record_ids[record_id] += 1
        candidate_ids[row.candidate_id] += 1
        semantic_group = row.quality.get("semantic_duplicate_group")
        structural_group = row.quality.get("structural_duplicate_group")
        if semantic_group:
            semantic_groups[str(semantic_group)] += 1
        if structural_group:
            structural_groups[str(structural_group)] += 1
        constructs |= detect_constructs(row.candidate_solution)
        edges |= set(row.fixture.get("edge_cases", [])) & RELEASE_EDGE_CASES

        verification = row.verification
        hidden = verification.get("hidden") or {}
        properties = verification.get("properties") or {}
        metamorphic = verification.get("metamorphic") or {}
        mutation = verification.get("mutation") or {}
        reasons = []
        if row.quality.get("decision") != "GOLDEN":
            reasons.append("quality decision is not GOLDEN")
        if (
            verification.get("verdict") != "PASS"
            or verification.get("verification_strength") != "STRONG"
        ):
            reasons.append("verification is not PASS/STRONG")
        if (
            mutation.get("mutation_score") != 1.0
            or int(mutation.get("applicable", 0)) < 1
            or int(mutation.get("survived", 0)) != 0
        ):
            reasons.append("valid semantic mutation evidence is insufficient")
        if (
            int(hidden.get("total", 0)) < 2
            or hidden.get("passed") != hidden.get("total")
            or int(hidden.get("failed", 0)) != 0
            or int(hidden.get("inconclusive", 0)) != 0
        ):
            reasons.append("hidden fixture evidence is incomplete")
        adversarial_cases = [
            case for case in hidden.get("cases", [])
            if case.get("source") == "INDEPENDENT_ADVERSARIAL"
        ]
        if len(adversarial_cases) != 1 or adversarial_cases[0].get("status") != "PASS":
            reasons.append("independent adversarial runtime case is missing or did not pass")
        if int(properties.get("applicable", 0)) < 1 or int(properties.get("failed", 0)) != 0:
            reasons.append("property evidence is incomplete")
        if int(metamorphic.get("applicable", 0)) < 1 or int(metamorphic.get("failed", 0)) != 0:
            reasons.append("metamorphic evidence is incomplete")
        if reasons:
            row_failures.append({"record_id": record_id, "reason": "; ".join(reasons)})
        if mutation.get("invalid") or mutation.get("inconclusive"):
            excluded_mutants.append(
                {
                    "record_id": record_id,
                    "invalid": mutation.get("invalid", 0),
                    "inconclusive": mutation.get("inconclusive", 0),
                }
            )
        for flag in row.quality.get("contamination_flags", []):
            if (
                flag.get("flag_type") == "EXACT_OVERLAP"
                and flag.get("scope") == "SAME_TASK_SIBLINGS"
                and not flag.get("hard")
            ):
                # This candidate-population flag is usually generated by
                # sibling SQL attempts for the same task. Selected-pool
                # collision gates below are the relevant release measure.
                sibling_overlap_flags.add(record_id)
            else:
                flagged_rows.add(record_id)

    family_counts = {family: families[family] for family in FAMILIES}
    missing_families = sorted(set(families) - set(FAMILIES))
    family_gate = not missing_families and all(count == 8 for count in family_counts.values())
    min_template_count = min((len(templates_by_family[family]) for family in FAMILIES), default=0)
    gates = {
        "row_count": _gate(len(rows), 80, len(rows) == 80),
        "family_balance": _gate(family_counts, "8 per family", family_gate),
        "construct_coverage": _gate(
            len(constructs), len(SQL_CONSTRUCTS), set(SQL_CONSTRUCTS) <= constructs
        ),
        "edge_coverage": _gate(
            len(edges), f"at least 15 of {len(RELEASE_EDGE_CASES)}", len(edges) >= 15
        ),
        "exact_instruction_variety": _gate(
            len(instructions),
            "at least 40; material difference still needs review",
            len(instructions) >= 40,
        ),
        "schema_variety": _gate(len(schemas), "at least 10", len(schemas) >= 10),
        "domain_variety": _gate(len(domains), "at least 5 explicit domains", len(domains) >= 5),
        "schema_concentration": _gate(
            max(schemas.values()), "at most 12 rows per schema", max(schemas.values()) <= 12
        ),
        "template_floor": _gate(
            min_template_count, "at least 4 IDs per family", min_template_count >= 4
        ),
        "one_selected_row_per_task": _gate(len(task_ids), len(rows), len(task_ids) == len(rows)),
        "unique_record_and_candidate_ids": _gate(
            {"records": len(record_ids), "candidates": len(candidate_ids)},
            len(rows),
            len(record_ids) == len(rows) and len(candidate_ids) == len(rows),
        ),
        "normalized_sql_text_variety": _gate(
            len(sql_shapes),
            "80 distinct normalized SQL texts; AST and semantic novelty not measured",
            len(sql_shapes) == len(rows),
        ),
        "selected_semantic_collision_members": _gate(
            sum(count for count in semantic_groups.values() if count > 1),
            "zero among selected rows; fingerprint is a screening heuristic",
            all(count == 1 for count in semantic_groups.values()),
        ),
        "selected_structural_collision_members": _gate(
            sum(count for count in structural_groups.values() if count > 1),
            "zero among selected rows; fingerprint is a screening heuristic",
            all(count == 1 for count in structural_groups.values()),
        ),
        "automated_row_evidence": _gate(len(row_failures), "zero failed rows", not row_failures),
        "unresolved_contamination_flags": _gate(
            len(flagged_rows), "zero or independently resolved", not flagged_rows
        ),
    }
    return {
        "source": str(source),
        "scope": "automated pre-review screen only",
        "automated_pre_review_gates_pass": all(gate["passed"] for gate in gates.values()),
        "gates": gates,
        "uncovered_constructs": sorted(set(SQL_CONSTRUCTS) - constructs),
        "uncovered_release_edges": sorted(RELEASE_EDGE_CASES - edges),
        "unrecognized_families": missing_families,
        "row_failures": row_failures,
        "excluded_mutants_for_inspection": excluded_mutants,
        "flagged_record_ids": sorted(flagged_rows),
        "candidate_sibling_exact_overlap_flags": len(sibling_overlap_flags),
        "not_measured": [
            "material semantic difference among instructions",
            "normalized SQL AST and semantic equivalence",
            "external benchmark contamination",
            "human validation of adversarial fixture design and independence",
            "schema and column description completeness",
            "full provenance graph and clean-environment replay",
            "schema relationship realism and empirical difficulty",
            "reviewer judgments, rights, clean-environment replay, and utility",
        ],
    }
