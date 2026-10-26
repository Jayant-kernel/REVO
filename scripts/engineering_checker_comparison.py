"""Freeze and execute a local, same-population checker comparison; never a scoring input."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.engineering_campaign import ROOT, safety
from scripts.engineering_qualification_receipts import profile
from scripts.engineering_receipt_artifacts import SUPPORTED
from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.sandbox import SandboxExecutor, load_config
from verified_data_factory.sandbox.docker import DockerRunner
from verified_data_factory.sandbox.models import RunResult
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.verification import verify_candidate
from verified_data_factory.verification.backend import DerivedTaskBackend
from verified_data_factory.verification.comparator import compare
from verified_data_factory.verification.oracle_registry import get_oracle
from verified_data_factory.verification.receipt_validation import (
    digest,
    required_sources,
    runtime_identity,
)

DECISIONS = {"execution_only": "SUCCEEDED with result data accepts; invalid SQL abstains",
             "ordinary_fixture": "typed authoritative result comparison on same initial execution",
             "full_verifier": "PASS accepts, FAIL rejects, INCONCLUSIVE/exception/infra failure abstains; strength reported separately"}


def write_new(path: Path, data: Any) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, default=str)


def sources() -> dict[str, str]:
    result = required_sources()
    for folder in ("scripts", "tests"):
        result.update({path.relative_to(ROOT).as_posix(): digest(path) for path in (ROOT / folder).rglob("*.py")})
    from scripts.engineering_qualification_receipts import INPUTS

    result.update({name: digest(ROOT / name) for name in INPUTS})
    return result


def population() -> list[dict[str, Any]]:
    cases = []
    registry = load_builtin_registry()
    for contract, version in sorted(SUPPORTED):
        alternatives, challenges, _ = profile(ROOT, contract, version)
        for label, entries in (("correct", alternatives), ("wrong", [sql for sql, _ in challenges])):
            for index, sql in enumerate(entries):
                cases.append({"id": f"{contract}@{version}:{label}:{index}", "contract": contract,
                    "version": version, "family": registry.get(contract, version).family,
                    "label": label, "sql": sql, "sql_sha256": hashlib.sha256(sql.encode()).hexdigest()})
    return cases


def freeze(path: Path, seed: int = 20123) -> None:
    if type(seed) is not int or seed < 0:
        raise ValueError("invalid reserved seed")
    write_new(path, {"version": 1, "created_at": datetime.now(UTC).isoformat(), "seed": seed,
        "scope": "supported profiles only; not full catalog, not frozen-rubric measurements",
        "authorship": "shared authoring; independent authorship unproven",
        "ground_truth": "reference alternatives and development witnessed wrong SQL; curated challenge set, not real-world prevalence",
        "reservation": f"{seed} ordinary fixture seed fixed before results; generator algorithms shared with development",
        "decisions": DECISIONS,
        "source_hashes": sources(), "runtime": runtime_identity(), "cases": population()})


def validate_protocol(data: dict[str, Any]) -> None:
    if (data.get("version") != 1 or type(data.get("seed")) is not int or data["seed"] < 0
            or not data.get("cases")):
        raise ValueError("missing/empty/unsupported frozen protocol")
    ids = [case["id"] for case in data["cases"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate comparison case")
    for case in data["cases"]:
        if (case["label"] not in {"correct", "wrong"} or (case["contract"], case["version"]) not in SUPPORTED
                or hashlib.sha256(case["sql"].encode()).hexdigest() != case["sql_sha256"]):
            raise ValueError("tampered comparison case")
    if data.get("runtime") != runtime_identity() or data.get("source_hashes") != sources():
        raise ValueError("stale/incomplete comparison dependency closure")
    if data["cases"] != population() or data.get("decisions") != DECISIONS:
        raise ValueError("substituted comparison population or decision rules")


class TracedRunner(DockerRunner):
    """The actual runner with append-only lifecycle observations, including cleanup."""

    def __init__(self, config: Any, path: Path) -> None:
        super().__init__(config)
        self.path = path
        self.cleanup_failures = 0

    def event(self, data: dict[str, Any]) -> None:
        import os

        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": datetime.now(UTC).isoformat(), **data}) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def run_container(self, name: str, execution_id: str, payload: bytes, timeout_s: float) -> RunResult:
        data = json.loads(payload)
        self.event({"phase": "start", "container": name, "execution_id": execution_id,
                    "payload_bytes": len(payload), "timeout_seconds": timeout_s,
                    "isolation_args": self._isolation_args(name, execution_id),
                    "payload_keys": sorted(data)})
        began = time.monotonic()
        try:
            result = super().run_container(name, execution_id, payload, timeout_s)
        except Exception as exc:
            self.event({"phase": "exception", "container": name, "exception_type": type(exc).__name__,
                        "elapsed_ms": int(1000*(time.monotonic()-began))})
            raise
        self.event({"phase": "returned", "container": name, "exit_code": result.exit_code,
                    "stdout_bytes": len(result.stdout), "stderr_bytes": len(result.stderr),
                    "elapsed_ms": int(1000*(time.monotonic()-began))})
        return result

    def remove(self, name: str) -> None:
        super().remove(name)
        try:
            inspected = subprocess.run(["docker", "container", "inspect", name], capture_output=True,
                                       text=True, timeout=15, check=False)
            absent = inspected.returncode != 0 and "No such" in inspected.stderr
        except (OSError, subprocess.TimeoutExpired):
            absent = False
        self.cleanup_failures += int(not absent)
        self.event({"phase": "cleanup", "container": name, "absence_confirmed": absent})


class TracedBackend(DerivedTaskBackend):
    def __init__(self, config: Any, executor: SandboxExecutor, directory: Path) -> None:
        super().__init__(config)
        self._executor = executor
        self.directory = directory
        self.calls = 0
        self.infrastructure_failures = 0

    def run(self, task: Any, candidate: Any, tables: Any, label: str) -> Any:
        self.calls += 1
        path = self.directory / f"backend-{self.calls:04d}.json"
        inputs = task.tables if tables is None else tables
        fields = {"label": label, "candidate_id": candidate.candidate_id,
                  "row_counts": {name: len(rows) for name, rows in inputs.items()}}
        try:
            result = super().run(task, candidate, tables, label)
        except Exception as exc:
            self.infrastructure_failures += 1
            write_new(path, {**fields, "exception_type": type(exc).__name__})
            raise
        self.infrastructure_failures += int(result.status in {"SANDBOX_ERROR", "TIMEOUT"})
        write_new(path, {**fields, "execution": result.model_dump(mode="json")})
        return result


def classify(label: str, decision: str) -> str:
    if label not in {"correct", "wrong"} or decision not in {"accept", "reject", "abstain"}:
        raise ValueError("unsupported label/decision")
    if decision == "abstain":
        return "abstention"
    return ("true_acceptance" if label == "correct" else "false_acceptance") if decision == "accept" else (
        "false_rejection" if label == "correct" else "true_rejection")


def summarize(rows: list[dict[str, Any]], population: int) -> dict[str, Any]:
    if population < 1 or len(rows) != population or len({row["id"] for row in rows}) != population:
        raise ValueError("empty/partial/duplicate comparison population")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    groups["overall"] = rows
    for row in rows:
        groups[row["family"]].append(row)
    return {name: {"population": len(members), "labels": dict(Counter(row["label"] for row in members)),
        "checkers": {checker: dict(Counter(classify(row["label"], row["decisions"][checker]) for row in members))
                     for checker in ("execution_only", "ordinary_fixture", "full_verifier")},
        "infrastructure_failures": sum(row["infra_failure"] for row in members),
        "invalid_initial_sql": sum(row["invalid_initial_sql"] for row in members),
        "checker_faults": sum(row.get("checker_fault", False) for row in members),
        "wall_seconds": sum(row["wall_seconds"] for row in members)} for name, members in groups.items()}


def run(protocol: Path, destination: Path) -> None:
    data = json.loads(protocol.read_text(encoding="utf-8"))
    validate_protocol(data)
    destination.mkdir(exist_ok=False)
    config = load_config(ROOT / "configs/sandbox_production.yaml")
    rows = []
    for index, case in enumerate(data["cases"]):
        directory = destination / f"case-{index:04d}"
        directory.mkdir()
        task = generate_task(load_builtin_registry().get(case["contract"], case["version"]), data["seed"])
        candidate = CandidateSolution(candidate_id=case["id"], task_id=task.task_id,
            model="reference-authored-checker-probe", model_revision="1", provider="manual",
            endpoint_id="none", prompt_version="no-model-call", generation_schema_version="1.0",
            candidate_index=index, raw_response=case["sql"], candidate_sql=case["sql"],
            generation_config={}, generation_timestamp=datetime.now(UTC).isoformat(), generation_duration_ms=0)
        write_new(directory / "task.json", task.model_dump(mode="json", by_alias=True))
        write_new(directory / "candidate.json", candidate.model_dump(mode="json"))
        runner = TracedRunner(config, directory / "lifecycle.jsonl")
        executor = SandboxExecutor(config, runner)
        backend = TracedBackend(config, executor, directory)
        began = time.monotonic()
        execution = executor.execute(task, candidate)
        write_new(directory / "initial-execution.json", execution.model_dump(mode="json"))
        success = execution.status == "SUCCEEDED" and execution.result_data is not None
        infra = execution.status in {"SANDBOX_ERROR", "TIMEOUT"}
        decisions = {"execution_only": "accept" if success else "abstain", "ordinary_fixture": "abstain",
                     "full_verifier": "abstain"}
        strength = "not_executed"
        checker_fault = False
        if success:
            result_data = execution.result_data
            assert result_data is not None
            expected = get_oracle(task.template_id, task.template_version).fn(task.requirements, task.tables)
            comparison = compare(expected, [column.name for column in result_data.columns], result_data.rows,
                                 column_types=[column.type for column in result_data.columns])
            write_new(directory / "ordinary-comparison.json", comparison.model_dump(mode="json"))
            decisions["ordinary_fixture"] = "accept" if comparison.match else "reject"
            try:
                verification = verify_candidate(task, candidate, execution, backend=backend)
                write_new(directory / "verification.json", verification.model_dump(mode="json"))
                decisions["full_verifier"] = {"PASS": "accept", "FAIL": "reject"}.get(verification.verdict, "abstain")
                strength = verification.verification_strength
            except Exception as exc:  # noqa: BLE001 — retain checker faults as abstentions, never semantic kills
                checker_fault = True
                write_new(directory / "verifier-exception.json", {"type": type(exc).__name__})
        infra = infra or backend.infrastructure_failures > 0 or runner.cleanup_failures > 0
        if infra:
            decisions["full_verifier"] = "abstain"
        row = {"id": case["id"], "family": case["family"], "label": case["label"], "decisions": decisions,
               "strength": strength, "initial_status": execution.status, "infra_failure": infra,
               "invalid_initial_sql": not success and not infra, "cleanup_failures": runner.cleanup_failures,
               "backend_calls": backend.calls, "checker_fault": checker_fault,
               "wall_seconds": time.monotonic()-began}
        rows.append(row)
        write_new(directory / "case-result.json", row)
        print(json.dumps(row), flush=True)
    validate_protocol(data)
    write_new(destination / "report.json", {"protocol_sha256": digest(protocol), "population": len(rows),
        "scope": data["scope"], "authorship": data["authorship"], "model_calls": 0,
        "paid_cost": 0, "compute_cost": "local wall time measured; monetary cost not measured",
        "rows": rows, "summary": summarize(rows, len(data["cases"]))})


def main() -> None:
    safety()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--seed", type=int, default=20123, help="Reserved ordinary-fixture seed; frozen before results")
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    if args.freeze:
        freeze(args.protocol, args.seed)
    elif args.destination is not None:
        run(args.protocol, args.destination)
    else:
        parser.error("--freeze or --destination required")


if __name__ == "__main__":
    main()
