"""Read-only diagnosis for the paused premium Phase 3 qualification run."""

from __future__ import annotations

# The package is source-local and not marked py.typed when this standalone script is checked.
# mypy: disable-error-code=import-untyped
import argparse
import hashlib
import json
import runpy
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from verified_data_factory.quality.duplicate_detection import (
    schema_fingerprint,
    semantic_key,
    sql_fingerprint,
)
from verified_data_factory.task_engine import (
    generate_task,
    load_builtin_registry,
    validate_task,
)
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.verification.adversarial import independent_adversarial_tables
from verified_data_factory.verification.mutations import applicable_operators
from verified_data_factory.verification.oracle_registry import ORACLES, get_oracle

RUN_FILES = (
    "candidates/attempt-reservations.jsonl",
    "candidates/candidates.jsonl",
    "execution/triples.jsonl",
    "manifests/run-manifest.json",
    "manifests/run-state.json",
    "quality/export/audit_required.jsonl",
    "quality/export/audit_sample.jsonl",
    "quality/export/dataset_health.json",
    "quality/export/excluded.jsonl",
    "quality/export/golden.jsonl",
    "quality/export/inconclusive.jsonl",
    "quality/export/population_metrics.json",
    "quality/export/review_queue.jsonl",
    "tasks/tasks.jsonl",
    "verification/verification.jsonl",
)


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _hashes(run: Path) -> dict[str, str]:
    return {
        relative.as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(run.rglob("*"))
        if path.is_file()
        for relative in [path.relative_to(run)]
    }


def _source(path: str, json_path: str) -> dict[str, str]:
    return {"file": path, "json_path": json_path}


def _reference_sql() -> dict[str, str]:
    """Load the existing hand-authored reference SQL without duplicating it."""
    root = Path(__file__).resolve().parents[1]
    sources = (
        root / "tests" / "test_business_tasks.py",
        root / "tests" / "test_legacy_adversarial.py",
    )
    combined: dict[str, str] = {}
    for source in sources:
        namespace = runpy.run_path(str(source))
        for name in ("SQL", "REFERENCE_SQL"):
            values = namespace.get(name, {})
            if isinstance(values, dict):
                combined.update({str(key): str(value) for key, value in values.items()})
    from verified_data_factory.verification.qualification.lowest_quote_profile import (
        CONTRACT,
        REFERENCE,
    )

    combined[CONTRACT] = REFERENCE
    from verified_data_factory.verification.qualification.delivery_profiles import (
        PROFILE_IDS,
        get_profile,
    )

    for contract, version in PROFILE_IDS:
        followup = get_profile(contract, version)
        assert followup is not None
        combined[contract] = followup.REFERENCE
    return combined


def _latest_templates() -> dict[str, Any]:
    registry = load_builtin_registry()
    latest: dict[str, Any] = {}
    for template in registry.list():
        if template.template_id not in latest or template.version > latest[template.template_id].version:
            latest[template.template_id] = template
    return latest


def _status(value: str, file: str, json_path: str) -> dict[str, Any]:
    return {"status": value, "source": _source(file, json_path)}


def _focused_test_ids() -> set[str]:
    root = Path(__file__).resolve().parents[1]
    focused: set[str] = set()
    for relative, names in (
        ("tests/test_business_tasks.py", ("SQL",)),
        ("tests/test_legacy_adversarial.py", ("REFERENCE_SQL",)),
    ):
        namespace = runpy.run_path(str(root / relative))
        for name in names:
            values = namespace.get(name, {})
            if isinstance(values, dict):
                focused.update(str(key) for key in values)
    return focused


def _candidate_rows(bundles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        result
        for bundle in bundles
        for result in bundle["results"]
    ]


def _semantic_groups(
    tasks: dict[str, dict[str, Any]], candidates: dict[str, dict[str, Any]]
) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for candidate_id, candidate in candidates.items():
        solution = candidate.get("candidate_solution")
        if not isinstance(solution, dict):
            continue
        task = tasks[solution["task_id"]]
        schema = task["schema"]
        fixture_counts = ",".join(
            f"{name}:{len(rows)}" for name, rows in sorted(task["tables"].items())
        )
        key = semantic_key(
            str(task["family"]),
            schema_fingerprint(schema),
            str(solution["candidate_sql"]),
            fixture_counts,
            ",".join(sorted(task.get("edge_cases", []))),
        )
        groups[key].append(candidate_id)
    return groups


def _stage_rows(
    tasks: dict[str, dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
    triples: dict[str, dict[str, Any]],
    verifications: dict[str, dict[str, Any]],
    excluded: dict[str, dict[str, Any]],
    golden: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate_id, result in candidates.items():
        solution = result.get("candidate_solution")
        task_id = solution.get("task_id") if isinstance(solution, dict) else None
        task = tasks.get(task_id or "")
        if task is None:
            continue
        verification = verifications.get(candidate_id, {})
        comparison = verification.get("comparison") or {}
        hidden = verification.get("hidden") or {}
        properties = verification.get("properties") or {}
        mutation = verification.get("mutation") or {}
        post_checks = bool(
            comparison.get("match")
            and hidden.get("failed", 0) == 0
            and hidden.get("inconclusive", 0) == 0
            and properties.get("failed", 0) == 0
            and mutation.get("mutation_score") == 1.0
        )
        reasons = excluded.get(candidate_id, {}).get("reasons", [])
        rows.append(
            {
                "candidate_id": candidate_id,
                "task_id": task_id,
                "family": task["family"],
                "template_id": task["template_id"],
                "generated": result.get("generation_status") == "success",
                "parseable": result.get("parse_status") == "success" and isinstance(solution, dict),
                "executed": candidate_id in triples,
                "initial_oracle_match": comparison.get("match") is True,
                "post_verification_pass": post_checks,
                "duplicate_excluded": any("DUPLICATE" in reason for reason in reasons),
                "selected": candidate_id in golden,
            }
        )
    return rows


def _yield_table(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    stages = (
        "generated",
        "parseable",
        "executed",
        "initial_oracle_match",
        "post_verification_pass",
        "duplicate_excluded",
        "selected",
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    report: dict[str, dict[str, Any]] = {}
    for name, members in sorted(grouped.items()):
        denominator = len(members)
        report[name] = {
            "candidates": denominator,
            "stages": {
                stage: {
                    "count": sum(bool(member[stage]) for member in members),
                    "rate": round(sum(bool(member[stage]) for member in members) / denominator, 6),
                }
                for stage in stages
            },
        }
    return report


def _duplicate_decomposition(
    tasks: dict[str, dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    groups = _semantic_groups(tasks, candidates)
    repeated = {key: ids for key, ids in groups.items() if len(ids) > 1}
    candidate_categories: Counter[str] = Counter()
    task_categories: defaultdict[str, set[str]] = defaultdict(set)
    cross_task_group_tasks: list[set[str]] = []
    for ids in repeated.values():
        task_ids = {candidates[candidate_id]["candidate_solution"]["task_id"] for candidate_id in ids}
        templates = {tasks[task_id]["template_id"] for task_id in task_ids}
        if len(task_ids) == 1:
            category = "sibling_same_task"
        elif len(templates) == 1:
            category = "same_template_cross_task"
            cross_task_group_tasks.append(task_ids)
        else:
            category = "cross_template_cross_task"
            cross_task_group_tasks.append(task_ids)
        candidate_categories[category] += len(ids)
        task_categories[category].update(task_ids)

    all_tasks = set(tasks)
    participating = set().union(*cross_task_group_tasks) if cross_task_group_tasks else set()
    sibling_excluded = participating
    same_template_excluded = set().union(
        *(
            task_ids
            for ids in repeated.values()
            for task_ids in [{candidates[c]["candidate_solution"]["task_id"] for c in ids}]
            if len(task_ids) > 1
            and len({tasks[task_id]["template_id"] for task_id in task_ids}) > 1
        )
    ) if repeated else set()
    return {
        "method": "Recomputed with quality.semantic_key; sibling-only groups never contribute to the task-level gate.",
        "task_level": {
            "total_tasks": len(all_tasks),
            "participating_tasks": len(participating),
            "rate": round(len(participating) / len(all_tasks), 6),
            "categories": {name: len(task_categories[name]) for name in sorted(task_categories)},
        },
        "candidate_level": {
            "total_candidates": len(candidates),
            "participating_candidates": sum(candidate_categories.values()),
            "rate": round(sum(candidate_categories.values()) / len(candidates), 6),
            "categories": dict(sorted(candidate_categories.items())),
        },
        "counterfactual": {
            "exclude_siblings": {
                "participating_tasks": len(sibling_excluded),
                "rate": round(len(sibling_excluded) / len(all_tasks), 6),
            },
            "exclude_siblings_and_same_template": {
                "participating_tasks": len(same_template_excluded),
                "rate": round(len(same_template_excluded) / len(all_tasks), 6),
            },
            "note": "Tautological retrospective: this reports the same observed semantic groups after excluding named categories from that same observation. It is not a causal estimate or prediction for a new run.",
        },
    }


def _funnel_triage(
    tasks: dict[str, dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
    triples: dict[str, dict[str, Any]],
    verifications: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate_id, candidate in sorted(candidates.items()):
        solution = candidate.get("candidate_solution")
        if not isinstance(solution, dict):
            continue
        task = tasks[solution["task_id"]]
        if task["family"] != "funnel":
            continue
        verification = verifications.get(candidate_id, {})
        execution = triples.get(candidate_id, {}).get("execution", {})
        comparison = verification.get("comparison") or {}
        if candidate_id not in triples:
            stage = "not_executed"
        elif execution.get("status") != "SUCCEEDED":
            stage = "execution"
        elif comparison.get("match") is False:
            stage = "initial_oracle_match"
        elif verification.get("verdict") != "PASS":
            stage = str(verification.get("failure_code") or "post_verification")
        else:
            stage = "selected_or_nonduplicate"
        label = "undetermined"
        if stage in {"execution", "initial_oracle_match"}:
            label = "model error"
        rows.append(
            {
                "candidate_id": candidate_id,
                "task_id": solution["task_id"],
                "template_id": task["template_id"],
                "failure_stage": stage,
                "label": label,
                "verification_failure_code": verification.get("failure_code"),
                "execution_failure": execution.get("failure"),
                "comparison_differences": comparison.get("differences", []),
                "oracle_expected": (verification.get("oracle") or {}).get("expected"),
                "historical_cross_check": "The artifact alone cannot prove an oracle bug or prompt ambiguity; syntax/output mismatches agree with the historical model-error categories where applicable.",
                "source": _source("verification/verification.jsonl", f"candidate_id={candidate_id}"),
            }
        )
    return rows


def _funnel_failure_mode(
    candidate_id: str, triples: dict[str, dict[str, Any]], verification: dict[str, Any]
) -> str:
    execution = triples.get(candidate_id, {}).get("execution", {})
    comparison = verification.get("comparison") or {}
    if execution.get("status") != "SUCCEEDED":
        return "execution_failed"
    if comparison.get("match") is False:
        return "result_mismatch"
    return "unknown"


def _funnel_label_audit(
    tasks: dict[str, dict[str, Any]],
    candidates: dict[str, dict[str, Any]],
    triples: dict[str, dict[str, Any]],
    verifications: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    funnel = _funnel_triage(tasks, candidates, triples, verifications)
    model_error = [item for item in funnel if item["label"] == "model error"]
    by_mode: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in model_error:
        by_mode[_funnel_failure_mode(item["candidate_id"], triples, verifications[item["candidate_id"]])].append(item)
    representative: list[dict[str, Any]] = []
    for mode, rows in sorted(by_mode.items()):
        for row in sorted(rows, key=lambda item: item["candidate_id"])[:3]:
            candidate = candidates[row["candidate_id"]]
            representative.append(
                {
                    "failure_mode": mode,
                    "candidate_id": row["candidate_id"],
                    "task_id": row["task_id"],
                    "template_id": row["template_id"],
                    "candidate_sql": candidate["candidate_solution"]["candidate_sql"],
                    "execution_failure": row["execution_failure"],
                    "comparison_differences": row["comparison_differences"],
                    "source": row["source"],
                }
            )

    hidden = [
        item
        for item in funnel
        if item["failure_stage"] == "HIDDEN_MISMATCH"
    ]
    hidden_inspections: list[dict[str, Any]] = []
    for item in sorted(hidden, key=lambda row: row["candidate_id"])[:2]:
        candidate = candidates[item["candidate_id"]]
        verification = verifications[item["candidate_id"]]
        task = tasks[item["task_id"]]
        hidden_inspections.append(
            {
                "candidate_id": item["candidate_id"],
                "task_id": item["task_id"],
                "template_id": item["template_id"],
                "primary_comparison_match": (verification.get("comparison") or {}).get("match"),
                "candidate_sql": candidate["candidate_solution"]["candidate_sql"],
                "instruction": task["instruction"],
                "hidden_cases": (verification.get("hidden") or {}).get("cases", []),
                "label": "unknown",
                "finding": "UNKNOWN: the frozen artifact records only hidden-case failure metadata, not the hidden fixture or expected/actual rows needed to distinguish a candidate defect from an oracle, fixture, or prompt defect.",
                "source": _source("verification/verification.jsonl", f"candidate_id={item['candidate_id']}"),
            }
        )
    return {
        "classification_rule": (
            "A funnel row is labelled 'model error' only when its stage is execution "
            "(candidate exists in execution/triples.jsonl and execution.status != 'SUCCEEDED') "
            "or initial_oracle_match (execution.status == 'SUCCEEDED' and "
            "verification.comparison.match is false). All other stages are 'undetermined'."
        ),
        "stage_derivation": "failure_stage is derived in _funnel_triage from execution/triples.jsonl before verification/verification.jsonl comparison fields; labels are then a pure function of that derived stage.",
        "source": [
            _source("execution/triples.jsonl", "$[*].execution.status"),
            _source("verification/verification.jsonl", "$[*].comparison.match"),
        ],
        "representative_candidate_diffs": representative,
        "hidden_mismatch_inspections": hidden_inspections,
    }


def _contract_readiness() -> dict[str, Any]:
    latest = _latest_templates()
    references = _reference_sql()
    focused = _focused_test_ids()
    rows: list[dict[str, Any]] = []
    unknown_reference_sql: list[str] = []
    for template_id, template in sorted(latest.items()):
        task = generate_task(template, 94001)
        validate_task(task)
        reference_sql = references.get(template_id)
        if reference_sql is None:
            unknown_reference_sql.append(template_id)
        oracle = get_oracle(template_id, template.version)
        statuses = {
            "template_validates": _status("yes", "templates/sql", f"{template_id}@{template.version} loaded by load_builtin_registry"),
            "fixture_generator": _status("yes", "src/verified_data_factory/task_engine/generator.py", "generate_task(template, 94001)"),
            "independent_oracle": _status(
                "yes" if oracle.strategy.startswith("independent_") else "no",
                "src/verified_data_factory/verification/oracle_registry.py",
                f"ORACLES[({template_id!r}, {template.version})].strategy={oracle.strategy}",
            ),
            "registry_entry": _status(
                "yes" if (template_id, template.version) in ORACLES else "no",
                "src/verified_data_factory/verification/oracle_registry.py",
                f"ORACLES[({template_id!r}, {template.version})]",
            ),
            "adversarial_case": _status(
                "yes" if independent_adversarial_tables(task) is not None else "no",
                "src/verified_data_factory/verification/adversarial.py",
                f"independent_adversarial_tables({template_id}@{template.version})",
            ),
            "reference_sql_mapping": _status(
                "yes" if reference_sql is not None else "unknown",
                "tests/test_business_tasks.py; tests/test_legacy_adversarial.py",
                f"SQL/REFERENCE_SQL[{template_id!r}]",
            ),
            "mutation_applicability": _status(
                "yes" if reference_sql is not None and applicable_operators(task, reference_sql, 10) else "unknown" if reference_sql is None else "no",
                "src/verified_data_factory/verification/mutations.py",
                f"applicable_operators({template_id}, reference_sql, 10)",
            ),
            "focused_test": _status(
                "yes" if template_id in focused else "no",
                "tests/test_business_tasks.py; tests/test_legacy_adversarial.py",
                f"parameterized contract test includes {template_id!r}",
            ),
        }
        rows.append({
            "family": template.family,
            "template_id": template_id,
            "template_version": template.version,
            "checks": statuses,
            "fully_verified": all(check["status"] == "yes" for check in statuses.values()),
        })
    by_family: dict[str, dict[str, Any]] = {}
    for family, members in sorted(
        ((family, [row for row in rows if row["family"] == family]) for family in {row["family"] for row in rows}),
    ):
        by_family[family] = {
            "fully_verified": sum(row["fully_verified"] for row in members),
            "templates": len(members),
            "summary": f"{sum(row['fully_verified'] for row in members)}/{len(members)} fully verified across 8 checks",
        }
    return {
        "columns": [
            "template_validates", "fixture_generator", "independent_oracle", "registry_entry",
            "adversarial_case", "reference_sql_mapping", "mutation_applicability", "focused_test",
        ],
        "rows": rows,
        "by_family": by_family,
        "unknown_reference_sql": unknown_reference_sql,
    }


def _task_survival(
    tasks: dict[str, dict[str, Any]], verifications: dict[str, dict[str, Any]], golden: set[str]
) -> dict[str, Any]:
    passed_tasks = {
        verification["task_id"]
        for verification in verifications.values()
        if verification.get("verdict") == "PASS"
    }
    golden_tasks = {
        verification["task_id"]
        for candidate_id, verification in verifications.items()
        if candidate_id in golden
    }
    def table(key: str) -> list[dict[str, Any]]:
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for task in tasks.values():
            groups[str(task[key])].append(task)
        return [
            {
                key: name,
                "tasks": len(members),
                "before_dedup_verification_pass": sum(task["task_id"] in passed_tasks for task in members),
                "after_dedup_selected_golden": sum(task["task_id"] in golden_tasks for task in members),
                "source": [
                    _source("verification/verification.jsonl", "$[?(@.verdict == 'PASS')].task_id"),
                    _source("quality/export/golden.jsonl", "$[*].candidate_id -> verification.task_id"),
                ],
            }
            for name, members in sorted(groups.items())
        ]
    return {"by_family": table("family"), "by_template": table("template_id")}


def _run_sql(task: Any, sql: str) -> dict[str, Any]:
    connection = materialize_duckdb(task.schema_, task.tables)
    try:
        cursor = connection.execute(sql)
        columns = [column[0] for column in cursor.description]
        rows = [list(row) for row in cursor.fetchall()]
        return {"columns": columns, "rows": rows}
    finally:
        connection.close()


def _contract_preflight() -> dict[str, Any]:
    latest = _latest_templates()
    references = _reference_sql()
    contracts: list[dict[str, Any]] = []
    for template_id, template in sorted(latest.items()):
        sql = references.get(template_id)
        if sql is None:
            contracts.append({
                "template_id": template_id,
                "family": template.family,
                "status": "UNKNOWN_REFERENCE_SQL",
                "source": "No hand-authored reference SQL was found in tests/test_business_tasks.py or tests/test_legacy_adversarial.py.",
            })
            continue
        task = generate_task(template, 94001)
        fixture_counts = ",".join(
            f"{name}:{len(rows)}" for name, rows in sorted(task.tables.items())
        )
        semantic = semantic_key(
            task.family,
            schema_fingerprint([table.model_dump(mode="json") for table in task.schema_]),
            sql,
            fixture_counts,
            ",".join(sorted(task.edge_cases)),
        )
        output = _run_sql(task, sql)
        contracts.append({
            "template_id": template_id,
            "family": template.family,
            "status": "MEASURED",
            "structural_fingerprint": sql_fingerprint(sql),
            "semantic_fingerprint": semantic,
            "schema_fingerprint": schema_fingerprint([table.model_dump(mode="json") for table in task.schema_]),
            "self_fixture_output_signature": hashlib.sha256(
                json.dumps(output, default=str, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "source": "tests/test_business_tasks.py:SQL or tests/test_legacy_adversarial.py:REFERENCE_SQL",
        })

    fingerprint_collisions: list[dict[str, Any]] = []
    self_fixture_output_coincidences: list[dict[str, Any]] = []
    measured = [contract for contract in contracts if contract["status"] == "MEASURED"]
    for left, right in combinations(measured, 2):
        if left["family"] != right["family"]:
            continue
        fingerprints = [
            name
            for name in ("structural_fingerprint", "semantic_fingerprint")
            if left[name] == right[name]
        ]
        pair = {"family": left["family"], "templates": [left["template_id"], right["template_id"]]}
        if fingerprints:
            fingerprint_collisions.append({**pair, "matching": fingerprints})
        if left["self_fixture_output_signature"] == right["self_fixture_output_signature"]:
            self_fixture_output_coincidences.append(pair)
    return {
        "contracts": contracts,
        "fingerprint_collisions": fingerprint_collisions,
        "self_fixture_output_coincidences": self_fixture_output_coincidences,
        "behavioral_signature_status": "UNKNOWN",
        "behavioral_signature_limitation": "The current contracts frequently have incompatible schemas. The output signature uses each contract's deterministic seed-94001 fixture, not a cross-contract shared probe; it is not behavioral-equivalence evidence.",
    }


def _decision_table(duplicate: dict[str, Any], funnel: list[dict[str, Any]], preflight: dict[str, Any]) -> list[dict[str, str]]:
    cross_template = duplicate["task_level"]["categories"].get("cross_template_cross_task", 0)
    model_errors = sum(item["label"] == "model error" for item in funnel)
    unknown = sum(item["label"] == "undetermined" for item in funnel)
    return [
        {
            "question": "Cross-template share of duplicate tasks",
            "measurement": f"{cross_template} task participants; source: recomputed semantic groups from candidates/candidates.jsonl and tasks/tasks.jsonl",
            "decision": "small" if cross_template == 0 else "large",
            "consequence": "Prioritize distinct-template scheduling and contract counts; this run does not show cross-template semantic-group collisions.",
        },
        {
            "question": "Funnel failure mix",
            "measurement": f"{model_errors} model-error labels, {unknown} undetermined labels; source: verification/verification.jsonl and execution/triples.jsonl",
            "decision": "model A/B plus execution-feedback retries",
            "consequence": "The recorded failures are predominantly candidate execution or oracle-result mismatches. Oracle and prompt correctness remain unknown without independent review.",
        },
        {
            "question": "Contract-level preflight collisions",
            "measurement": f"{len(preflight['fingerprint_collisions'])} structural/semantic fingerprint collisions; behavioral signatures {preflight['behavioral_signature_status']}",
            "decision": "no contract change justified by current fingerprints",
            "consequence": "Do not treat same-fixture output coincidences as behavioral duplicates. Add a shared-probe protocol before relying on behavioral collision claims.",
        },
    ]


def _markdown(report: dict[str, Any]) -> str:
    totals = report["reconciliation"]
    duplicate = report["duplicate_decomposition"]
    funnel = report["funnel_triage"]
    readiness = report["contract_readiness"]
    survival = report["task_survival"]
    audit = report["funnel_label_audit"]
    lines = [
        "# Phase 3 Diagnostic",
        "",
        "## Scope",
        "",
        "Read-only analysis of `runs/premium-qualification-080`. No generation, execution of candidate SQL, or modification of run artifacts occurred.",
        "",
        "## Reconciliation",
        "",
        f"- Candidates: {totals['candidates']['actual']} (source: {totals['candidates']['source']['file']} {totals['candidates']['source']['json_path']})",
        f"- Verification passes: {totals['verification_passes']['actual']} (source: {totals['verification_passes']['source']['file']} {totals['verification_passes']['source']['json_path']})",
        f"- Semantic-duplicate exclusions: {totals['semantic_duplicate_exclusions']['actual']} (source: {totals['semantic_duplicate_exclusions']['source']['file']} {totals['semantic_duplicate_exclusions']['source']['json_path']})",
        f"- Selected Goldens: {totals['selected_goldens']['actual']} (source: {totals['selected_goldens']['source']['file']} {totals['selected_goldens']['source']['json_path']})",
        "",
        "## Duplicate Decomposition",
        "",
        f"- Task level: {duplicate['task_level']['participating_tasks']}/{duplicate['task_level']['total_tasks']} = {duplicate['task_level']['rate']:.1%}",
        f"- Candidate level: {duplicate['candidate_level']['participating_candidates']}/{duplicate['candidate_level']['total_candidates']} = {duplicate['candidate_level']['rate']:.1%}",
        f"- Counterfactual excluding siblings: {duplicate['counterfactual']['exclude_siblings']['rate']:.1%}",
        f"- Counterfactual excluding siblings and same-template collisions: {duplicate['counterfactual']['exclude_siblings_and_same_template']['rate']:.1%}",
        f"- {duplicate['counterfactual']['note']}",
        "",
        "## Contract Readiness",
        "",
        "Statuses are `yes`, `no`, or `unknown`; every cell's source is in the JSON report.",
        "",
        "| Family | Fully verified | Templates |",
        "| --- | --- | --- |",
    ]
    for family, summary in readiness["by_family"].items():
        lines.append(f"| {family} | {summary['fully_verified']}/{summary['templates']} | {summary['summary']} |")
    lines.extend([
        "",
        "| Template | Template validates | Fixture generator | Independent oracle | Registry entry | Adversarial case | Reference SQL mapping | Mutation applicability | Focused test | Fully verified |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for row in readiness["rows"]:
        checks = row["checks"]
        cells = " | ".join(checks[name]["status"] for name in readiness["columns"])
        lines.append(f"| {row['template_id']} | {cells} | {'yes' if row['fully_verified'] else 'no'} |")
    lines.extend([
        "",
        "### UNKNOWN_REFERENCE_SQL",
        "",
        *[f"- `{template_id}`" for template_id in readiness["unknown_reference_sql"]],
        "",
        "## Task Survival",
        "",
        "A task survives before dedup if at least one candidate has verification verdict `PASS`; after dedup it survives when selected Golden.",
        "",
        "| Family | Tasks | Before dedup PASS | After dedup selected Golden |",
        "| --- | --- | --- | --- |",
    ])
    for row in survival["by_family"]:
        lines.append(f"| {row['family']} | {row['tasks']} | {row['before_dedup_verification_pass']} | {row['after_dedup_selected_golden']} |")
    lines.extend([
        "",
        "| Template | Tasks | Before dedup PASS | After dedup selected Golden |",
        "| --- | --- | --- | --- |",
    ])
    for row in survival["by_template"]:
        lines.append(f"| {row['template_id']} | {row['tasks']} | {row['before_dedup_verification_pass']} | {row['after_dedup_selected_golden']} |")
    lines.extend([
        "",
        "## Funnel Triage",
        "",
        f"- Classification rule: {audit['classification_rule']}",
        f"- Derivation proof: {audit['stage_derivation']}",
        "",
    ])
    for item in funnel:
        lines.append(f"- `{item['candidate_id']}`: {item['failure_stage']}; {item['label']}")
    lines.extend([
        "",
        "### Representative Model-Error Diffs",
        "",
    ])
    for item in audit["representative_candidate_diffs"]:
        lines.append(f"- `{item['candidate_id']}`: {item['failure_mode']}; execution={item['execution_failure']}; differences={item['comparison_differences']}")
    lines.extend([
        "",
        "### Hidden Mismatch Inspections",
        "",
    ])
    for item in audit["hidden_mismatch_inspections"]:
        lines.append(f"- `{item['candidate_id']}`: {item['label']}; {item['finding']}")
    lines.extend([
        "",
        "## Open Questions",
        "",
        "- Oracle semantic correctness requires independent human/domain review; existing artifacts cannot establish it.",
        "- Prompt ambiguity cannot be distinguished from model error solely from recorded candidate outputs.",
        "- Cross-schema behavioral equivalence is unknown because the catalog has no shared probe-fixture protocol.",
        "",
        "Full machine-readable sections, sources, and collision detail are in the adjacent JSON report.",
    ])
    return "\n".join(lines) + "\n"


def build_report(run: Path) -> dict[str, Any]:
    before_hashes = _hashes(run)
    missing = [path for path in RUN_FILES if path not in before_hashes]
    if missing:
        raise ValueError(f"run is missing required artifacts: {missing}")
    bundles = _read_jsonl(run / "candidates/candidates.jsonl")
    candidate_list = _candidate_rows(bundles)
    candidates = {
        item["candidate_solution"]["candidate_id"]: item
        for item in candidate_list
        if isinstance(item.get("candidate_solution"), dict)
    }
    tasks_list = _read_jsonl(run / "tasks/tasks.jsonl")
    tasks = {item["task_id"]: item for item in tasks_list}
    triples_list = _read_jsonl(run / "execution/triples.jsonl")
    triples = {item["candidate"]["candidate_id"]: item for item in triples_list}
    verification_list = _read_jsonl(run / "verification/verification.jsonl")
    verifications = {item["candidate_id"]: item for item in verification_list}
    excluded_list = _read_jsonl(run / "quality/export/excluded.jsonl")
    excluded = {item["candidate_id"]: item for item in excluded_list}
    golden_list = _read_jsonl(run / "quality/export/golden.jsonl")
    golden = {item["candidate_id"] for item in golden_list}
    health = _read_json(run / "quality/export/dataset_health.json")
    population = _read_json(run / "quality/export/population_metrics.json")

    rows = _stage_rows(tasks, candidates, triples, verifications, excluded, golden)
    semantic_duplicate_exclusions = sum(
        "SEMANTIC_DUPLICATE" in item.get("reasons", []) for item in excluded_list
    )
    verification_passes = sum(item.get("verdict") == "PASS" for item in verification_list)
    reconciliation = {
        "candidates": {"expected": 240, "actual": len(candidates), "source": _source("candidates/candidates.jsonl", "$[*].results[*]")},
        "verification_passes": {"expected": 128, "actual": verification_passes, "source": _source("verification/verification.jsonl", "$[?(@.verdict == 'PASS')]")},
        "semantic_duplicate_exclusions": {"expected": 85, "actual": semantic_duplicate_exclusions, "source": _source("quality/export/excluded.jsonl", "$[?('SEMANTIC_DUPLICATE' in @.reasons)]")},
        "selected_goldens": {"expected": 37, "actual": len(golden), "source": _source("quality/export/golden.jsonl", "$[*]")},
        "all_expected_totals_match": len(candidates) == 240 and verification_passes == 128 and semantic_duplicate_exclusions == 85 and len(golden) == 37,
    }
    duplicate = _duplicate_decomposition(tasks, candidates)
    funnel = _funnel_triage(tasks, candidates, triples, verifications)
    preflight = _contract_preflight()
    readiness = _contract_readiness()
    survival = _task_survival(tasks, verifications, golden)
    funnel_audit = _funnel_label_audit(tasks, candidates, triples, verifications)
    after_hashes = _hashes(run)
    return {
        "report_version": "1.1",
        "run": str(run.as_posix()),
        "source_hashes_before": before_hashes,
        "source_hashes_after": after_hashes,
        "run_files_unchanged": before_hashes == after_hashes,
        "reconciliation": reconciliation,
        "yield_by_family": _yield_table(rows, "family"),
        "yield_by_template": _yield_table(rows, "template_id"),
        "duplicate_decomposition": duplicate,
        "funnel_triage": funnel,
        "funnel_label_audit": funnel_audit,
        "contract_preflight": preflight,
        "contract_readiness": readiness,
        "task_survival": survival,
        "decision_table": _decision_table(duplicate, funnel, preflight),
        "artifact_cross_checks": {
            "task_duplicate_rate": {"reported": population["candidate_population"]["cross_task_semantic_duplicate_rate"], "recomputed": duplicate["task_level"]["rate"], "source": _source("quality/export/population_metrics.json", "$.candidate_population.cross_task_semantic_duplicate_rate")},
            "candidate_duplicate_rate": {"reported": health["duplicates"]["semantic_duplicate_rate"], "recomputed": duplicate["candidate_level"]["rate"], "source": _source("quality/export/dataset_health.json", "$.duplicates.semantic_duplicate_rate")},
        },
        "open_questions": [
            "Independent human review of oracle/business-rule correctness is unknown.",
            "Prompt ambiguity is unknown from existing artifacts.",
            "Cross-schema behavioral-equivalence testing is unknown without a shared probe-fixture protocol.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="runs/premium-qualification-080")
    parser.add_argument("--output-dir", default="docs/production")
    parser.add_argument("--stem", default="phase3-diagnostic-20261002")
    args = parser.parse_args()
    report = build_report(Path(args.run))
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    (output_dir / f"{args.stem}.json").write_text(encoded, encoding="utf-8")
    (output_dir / f"{args.stem}.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"json": str(output_dir / f"{args.stem}.json"), "run_files_unchanged": report["run_files_unchanged"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
