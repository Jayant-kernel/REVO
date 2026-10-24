"""Recompute schema-v2 details. A coherent execution record is not an attestation."""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import math
import platform
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Sequence
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import Timer
from types import TracebackType
from typing import Any, Self

import duckdb

from verified_data_factory.generation.models import CandidateSolution
from verified_data_factory.local_paths import io_path
from verified_data_factory.sandbox.executor import build_execution_id
from verified_data_factory.sandbox.models import ExecutionResult
from verified_data_factory.sandbox.policy import check_policy
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.task_engine.hidden_fixtures import (
    diverse_hidden_tables,
    fixture_fingerprint,
    materialized_fixture_fingerprint,
    materialized_fixture_tables,
)
from verified_data_factory.task_engine.models import TaskInstance

from ..behavior_authority import PublicBehaviorMap, public_behavior_map
from ..comparator import compare
from ..metamorphic import contract_relation_tables
from ..models import COMPARISON_VERSION, ComparisonPolicy
from ..oracle_registry import get_oracle
from ..receipt_models import (
    ArtifactRef,
    ChallengeDetail,
    FixtureDetail,
    FixtureWitness,
    FuzzDetail,
    FuzzObservation,
    MutationDetail,
    NamedTestsDetail,
    ReceiptV2,
    RelationsDetail,
    RulesDetail,
    SQLWitness,
)
from ..receipt_observations import observation_fixture, observed_behaviors
from .public_rule_proofs import public_proofs, schema_checks, schema_invalid

TIMESTAMP_DURATION_EPSILON_MS = 1
SUCCESS_TIMEOUT_OVERHEAD_MS = 250


def encode(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def confined(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root.resolve()):
        raise ValueError("artifact path escapes root")
    return path


def artifact(root: Path, reference: ArtifactRef) -> Path:
    path = io_path(confined(root, reference.path))
    if not path.is_file() or digest(path) != reference.sha256:
        raise ValueError("missing or stale artifact")
    return path


def read_json(root: Path, reference: ArtifactRef) -> Any:
    return json.loads(artifact(root, reference).read_text(encoding="utf-8"))


def required_sources() -> dict[str, str]:
    """Conservative core closure; producer-specific inputs must be added separately."""
    live = Path(__file__).resolve().parents[4]
    files = list((live / "src").rglob("*.py"))
    files += list((live / "templates/sql").rglob("*.yaml"))
    files += list((live / "templates/sql").rglob("*.yml"))
    files += [live / "configs/package_a/engineering-rubric.json",
              live / "scripts/package_a_evidence.py"]
    return {p.relative_to(live).as_posix(): digest(p) for p in files}


def runtime_identity() -> dict[str, str]:
    return {"python": platform.python_version(), "platform": platform.platform(),
            **{name: importlib.metadata.version(name) for name in
               ("duckdb", "pydantic", "pyyaml", "pyarrow", "pytest", "hypothesis")}}


def validate_sources(root: Path, receipt: ReceiptV2) -> dict[str, Any]:
    if receipt.runtime != runtime_identity():
        raise ValueError("missing or stale runtime dependency identity")
    required = required_sources()
    if any(receipt.source_hashes.get(p) != sha for p, sha in required.items()):
        raise ValueError("missing or stale core source dependency")
    if receipt.producer not in receipt.source_hashes or not receipt.producer.endswith(".py"):
        raise ValueError("producer source binding missing")
    for relative, sha in receipt.source_hashes.items():
        artifact(root, ArtifactRef(path=relative, sha256=sha))
    rubric = json.loads(confined(root, "configs/package_a/engineering-rubric.json").read_text())
    return dict(rubric["thresholds"])


class DetailValidator:
    def __init__(
        self, root: Path, task: TaskInstance, authority: PublicBehaviorMap,
        sources: dict[str, str], thresholds: dict[str, Any],
    ) -> None:
        self.root, self.task, self.authority = root, task, authority
        self.sources, self.thresholds = sources, thresholds
        self.executions: dict[str, str] = {}
        self.run_count = 0
        self._scope_depth = 0
        self._fixture_key = ""
        self._fixture_tables: dict[str, list[dict[str, Any]]] = {}
        self._connection: duckdb.DuckDBPyConnection | None = None
        self._verified_sql: set[str] = set()

    def __enter__(self) -> Self:
        if self._scope_depth == 0:
            self.executions.clear()
            self.run_count = 0
        self._scope_depth += 1
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._scope_depth -= 1
        if self._scope_depth == 0:
            self.close()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        self._fixture_key = ""
        self._fixture_tables = {}
        self._verified_sql.clear()

    def _key(self, witness: FixtureWitness | SQLWitness) -> str:
        oracle = get_oracle(self.task.template_id, self.task.template_version)
        payload = encode([witness.model_dump(mode="json"),
                          self.task.model_dump(mode="json", by_alias=True),
                          oracle.oracle_version, COMPARISON_VERSION, duckdb.__version__])
        return hashlib.sha256(payload.encode()).hexdigest()

    def tables(self, reference: ArtifactRef) -> dict[str, list[dict[str, Any]]]:
        tables: dict[str, list[dict[str, Any]]] = read_json(self.root, reference)
        if not isinstance(tables, dict) or set(tables) != {t.name for t in self.task.schema_}:
            raise ValueError("fixture schema/table binding mismatch")
        for table in self.task.schema_:
            rows = tables[table.name]
            if not isinstance(rows, list) or len(rows) > 100_000:
                raise ValueError("fixture row domain exceeded")
            if any(not isinstance(r, dict) or set(r) != {c.name for c in table.columns}
                   for r in rows):
                raise ValueError("fixture row/column binding mismatch")
        return tables

    def fixture(self, witness: FixtureWitness) -> dict[str, list[dict[str, Any]]]:
        # Rehash even cache hits: paths/hashes alone do not attest current contents.
        artifact(self.root, witness.tables)
        key = self._key(witness)
        if self._scope_depth and key == self._fixture_key:
            return deepcopy(self._fixture_tables)
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            self._fixture_key, self._fixture_tables = "", {}
        tables = self.tables(witness.tables)
        # Fingerprinting/replay apply declared DuckDB types. The oracle must see
        # those same cells, not raw JSON spellings with different Python meaning.
        connection = materialize_duckdb(self.task.schema_, tables)
        try:
            tables = materialized_fixture_tables(self.task, connection)
            if materialized_fixture_fingerprint(self.task, connection) != witness.fingerprint:
                raise ValueError("fixture fingerprint mismatch")
            expected = get_oracle(self.task.template_id, self.task.template_version).fn(
                self.task.requirements, tables,
            )
            if encode(expected.model_dump(mode="json")) != encode(witness.expected.model_dump(mode="json")):
                raise ValueError("fixture expected result differs from current oracle")
            if self._scope_depth:
                connection.execute("SET enable_external_access = false")
                connection.execute("SET threads = 1")
                connection.execute("SET memory_limit = '128MB'")
                if self._connection is not None:
                    self._connection.close()
                self._connection = connection
                self._fixture_key, self._fixture_tables = key, deepcopy(tables)
            else:
                connection.close()
        except BaseException:
            connection.close()
            raise
        return tables

    def sql(self, witness: SQLWitness) -> tuple[str, dict[str, list[dict[str, Any]]]]:
        tables = self.fixture(witness.fixture)
        sql = artifact(self.root, witness.sql).read_text(encoding="utf-8")
        artifact(self.root, witness.candidate)
        artifact(self.root, witness.execution)
        key = self._key(witness)
        if self._scope_depth and key in self._verified_sql:
            return sql, tables
        candidate = CandidateSolution.model_validate(read_json(self.root, witness.candidate))
        execution = ExecutionResult.model_validate(read_json(self.root, witness.execution))
        if candidate.task_id != self.task.task_id or candidate.candidate_sql != sql:
            raise ValueError("candidate/task/SQL binding mismatch")
        if candidate.generation_status != "success" or candidate.parse_status != "success":
            raise ValueError("unsuccessful candidate generation")
        data = execution.result_data
        if (execution.task_id != self.task.task_id or execution.candidate_id != candidate.candidate_id
                or execution.execution_id != build_execution_id(candidate.candidate_id, execution.started_at)
                or execution.status != "SUCCEEDED" or execution.failure is not None
                or execution.exit_code != 0 or data is None or data.truncated
                or execution.stdout_truncated or execution.stderr_truncated):
            raise ValueError("unsuccessful or inconsistent retained execution")
        if (data.rows_returned != len(data.rows)
                or any(len(row) != len(data.columns) for row in data.rows)
                or execution.duration_ms != execution.resource_usage.duration_ms
                or datetime.fromisoformat(execution.finished_at) < datetime.fromisoformat(execution.started_at)
                or execution.duckdb_version != duckdb.__version__):
            raise ValueError("execution detail consistency mismatch")
        started = datetime.fromisoformat(execution.started_at)
        finished = datetime.fromisoformat(execution.finished_at)
        if started.tzinfo is None or finished.tzinfo is None:
            raise ValueError("execution timestamp/duration accounting mismatch")
        elapsed_ms = (finished - started).total_seconds() * 1000
        if abs(execution.duration_ms - elapsed_ms) > TIMESTAMP_DURATION_EPSILON_MS:
            raise ValueError("execution timestamp/duration accounting mismatch")
        limits = execution.resource_limits
        if (not math.isfinite(limits.timeout_seconds) or not math.isfinite(limits.cpus)
                or limits.timeout_seconds <= 0 or limits.memory_mb <= 0 or limits.cpus <= 0
                or limits.pids_limit < 1 or limits.max_result_rows < len(data.rows)
                or limits.max_stdout_bytes < 0 or limits.max_stderr_bytes < 0):
            raise ValueError("execution resource details inconsistent with successful result")
        # Executor wall time includes staging/collection around the timed run.
        # Only a fixed bounded overhead is tolerated, not arbitrary elapsed time.
        if elapsed_ms > limits.timeout_seconds * 1000 + SUCCESS_TIMEOUT_OVERHEAD_MS:
            raise ValueError("successful execution exceeds timeout accounting budget")
        memory = execution.resource_usage.max_memory_mb
        if memory is not None and (not math.isfinite(memory) or memory < 0 or memory > limits.memory_mb):
            raise ValueError("execution measured memory exceeds resource limit")
        if len(execution.stdout.encode("utf-8")) > limits.max_stdout_bytes:
            raise ValueError("execution retained stdout exceeds byte limit")
        if len(execution.stderr.encode("utf-8")) > limits.max_stderr_bytes:
            raise ValueError("execution retained stderr exceeds byte limit")
        # Match SandboxExecutor._success's JSON defaults, column-count header and
        # UTF-8 encoding, not the receipt envelope or compact/sorted JSON.
        output_bytes = len(json.dumps({"columns": len(data.columns), "rows": data.rows},
                                     default=str).encode("utf-8"))
        if execution.resource_usage.output_bytes != output_bytes:
            raise ValueError("execution output byte accounting mismatch")
        if output_bytes > limits.max_result_bytes:
            raise ValueError("execution resource details inconsistent with successful result")
        identity = encode([witness.sql.sha256, witness.fixture.fingerprint, witness.execution.sha256])
        prior = self.executions.get(execution.execution_id)
        if prior is not None and prior != identity:
            raise ValueError("execution ID reused for different SQL/fixture/result")
        if not check_policy(sql).allowed:
            raise ValueError("invalid SQL execution policy")
        # Replay cannot access host files/extensions; memory, row and time bounded.
        con = self._connection if self._scope_depth else materialize_duckdb(self.task.schema_, tables)
        assert con is not None
        timer = Timer(5, con.interrupt)
        transaction_started = False
        try:
            con.execute("SET enable_external_access = false")
            con.execute("SET threads = 1")
            con.execute("SET memory_limit = '128MB'")
            statements = con.extract_statements(sql)
            if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
                raise ValueError("invalid SQL execution policy")
            con.execute("BEGIN TRANSACTION")
            transaction_started = True
            timer.start()
            cursor = con.execute(sql)
            observed = [[str(v) if isinstance(v, datetime) else v for v in row]
                        for row in cursor.fetchmany(100_001)]
            if len(observed) > 100_000:
                raise ValueError("execution replay row limit exceeded")
            columns = [{"name": c[0], "type": str(c[1])} for c in cursor.description]
            if encode(columns) != encode([c.model_dump() for c in data.columns]) or encode(observed) != encode(data.rows):
                raise ValueError("retained output differs from actual SQL replay")
        except duckdb.Error as exc:
            raise ValueError("SQL replay failed; not a semantic witness") from exc
        finally:
            timer.cancel()
            if timer.ident is not None:
                timer.join()
            try:
                if transaction_started:
                    con.execute("ROLLBACK")
            finally:
                if not self._scope_depth:
                    con.close()
        comparison = compare(witness.fixture.expected, [c.name for c in data.columns],
                             data.rows, column_types=[c.type for c in data.columns])
        if witness.comparison.policy != ComparisonPolicy():
            raise ValueError("non-authoritative comparison policy")
        if encode(comparison.model_dump(mode="json")) != encode(witness.comparison.model_dump(mode="json")):
            raise ValueError("retained comparison differs from recomputation")
        if comparison.match != (witness.outcome == "MATCH"):
            raise ValueError("SQL outcome differs from recomputed comparison")
        self.executions[execution.execution_id] = identity
        if self._scope_depth:
            self._verified_sql.add(key)
        self.run_count = len(self.executions)
        return sql, tables

    def named_tests(self, detail: NamedTestsDetail) -> tuple[int, dict[str, Any]]:
        path = artifact(self.root, detail.report)
        text = path.read_text(encoding="utf-8")
        if "<!DOCTYPE" in text or "<!ENTITY" in text:
            raise ValueError("unsupported test report declarations")
        report = ET.fromstring(text)
        suites = list(report.iter("testsuite"))
        if not suites:
            raise ValueError("terminal test suites missing")
        for suite in suites:
            cases = list(suite.iter("testcase"))
            totals = {"tests": len(cases), "failures": sum(c.find("failure") is not None for c in cases),
                      "errors": sum(c.find("error") is not None for c in cases),
                      "skipped": sum(c.find("skipped") is not None for c in cases)}
            if any(int(suite.attrib.get(k, "-1")) != value for k, value in totals.items()):
                raise ValueError("test report terminal summary differs from testcase outcomes")
            if totals["failures"] or totals["errors"]:
                raise ValueError("test report terminal outcome is nonpassing")
        nodes: dict[str, str] = {}
        for case in report.iter("testcase"):
            raw_properties = case.findall("properties/property")
            properties = {p.attrib["name"]: p.attrib["value"] for p in raw_properties}
            if len(properties) != len(raw_properties):
                raise ValueError("duplicate test report properties")
            if properties.get("contract_id") != self.task.template_id or properties.get("contract_version") != str(self.task.template_version):
                continue
            node = properties.get("node_id", "")
            parts = node.split("::")
            if len(parts) < 2 or parts[0] not in self.sources or node in nodes:
                raise ValueError("missing, duplicate or unbound exact named test node")
            tree = ast.parse(confined(self.root, parts[0]).read_text(encoding="utf-8"))
            children = tree.body
            for name in parts[1:]:
                name = name.split("[", 1)[0]
                selected = [n for n in children if isinstance(n, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) and n.name == name]
                if len(selected) != 1:
                    raise ValueError("named test node absent from bound test source")
                children = selected[0].body
            if case.attrib.get("name") != parts[-1] or not parts[-1].startswith("test_"):
                raise ValueError("test report exact name/node mismatch")
            classname = parts[0].removesuffix(".py").replace("/", ".")
            if parts[1:-1]:
                classname += "." + ".".join(parts[1:-1])
            if case.attrib.get("classname") != classname:
                raise ValueError("test report exact class/node mismatch")
            nodes[node] = next((tag for tag in ("error", "failed", "skipped")
                                if case.find("failure" if tag == "failed" else tag) is not None), "passed")
        if not nodes or nodes != detail.nodes or any(v != "passed" for v in nodes.values()):
            raise ValueError("named test report outcomes/counts mismatch or nonpassing")
        if not any("pytest" in arg for arg in detail.command):
            raise ValueError("named test terminal command missing")
        return len(nodes), {"passed": len(nodes), "failed": 0}

    def fixtures(self, detail: FixtureDetail) -> tuple[int, dict[str, Any]]:
        for fixture in detail.fixtures:
            self.fixture(fixture)
            if fixture.origin == "seed":
                seeds = self.thresholds["hidden_seeds"]
                if fixture.seed is None or fixture.seed not in seeds:
                    raise ValueError("fixture seed coverage incomplete")
                generated = diverse_hidden_tables(self.task, fixture.seed, seeds.index(fixture.seed) + 1)
                if fixture.fingerprint != fixture_fingerprint(self.task, generated):
                    raise ValueError("fixture differs from declared canonical seed generation")
        fingerprints = {f.fingerprint for f in detail.fixtures}
        if len(fingerprints) != len(detail.fixtures) or len(fingerprints) < self.thresholds["minimum_distinct_fixtures_including_original"]:
            raise ValueError("fixture diversity incomplete")
        if not any(f.origin == "original" and f.fingerprint == fixture_fingerprint(self.task, self.task.tables) for f in detail.fixtures):
            raise ValueError("original fixture missing")
        seeds = {f.seed for f in detail.fixtures if f.origin == "seed"}
        if None in seeds or seeds != set(self.thresholds["hidden_seeds"]):
            raise ValueError("fixture seed coverage incomplete")
        outputs = [f.expected.rows for f in detail.fixtures]
        if not any(outputs) or len({encode(o) for o in outputs}) < 2:
            raise ValueError("vacuous or constant-output fixture suite")
        return len(detail.fixtures), {"distinct_contents": len(fingerprints), "seed_cases": len(seeds)}

    def rules(self, detail: RulesDetail) -> tuple[int, dict[str, Any]]:
        self.authority = public_behavior_map(self.task)
        public = {r.rule_id: r for r in self.authority.rules}
        if len({r.rule_id for r in detail.rules}) != len(detail.rules) or {r.rule_id for r in detail.rules} != set(public):
            raise ValueError("detailed rule map differs from complete public ledger")
        for rule in detail.rules:
            declaration = public[rule.rule_id]
            if rule.kind != declaration.kind or rule.declaration_json != declaration.declaration_json:
                raise ValueError("invented rule declaration or domain waiver")
            if rule.disposition == "BLOCKED":
                raise ValueError(f"blocked public behavior obligation: {rule.rule_id}")
            if rule.source_clause != declaration.source_clause:
                raise ValueError("rule source attribution differs from public clause")
            disposition = "SEMANTIC_DISCRIMINATOR" if rule.kind == "semantic" else "DOMAIN_REJECTION"
            if declaration.kind == "structural":
                disposition = "STRUCTURAL_DISCRIMINATOR"
            if declaration.proof_key == "schema" and json.loads(declaration.declaration_json)["nullable"]:
                disposition = "DOMAIN_CONFORMANCE"
            if rule.blocked_reason or rule.disposition != disposition:
                raise ValueError("rule disposition differs from public semantic/domain kind")
        reference, proofs = self.rule_proofs()
        for rule in detail.rules:
            declaration = public[rule.rule_id]
            if rule.kind == "structural":
                from .structural import structural_checks

                if (rule.correct is None or rule.wrong is None or rule.invalid_tables is not None
                        or rule.domain_tables is not None or rule.domain_checks or rule.rejection):
                    raise ValueError("structural obligation requires executed correct/equivalent control")
                correct_sql, _ = self.sql(rule.correct)
                wrong_sql, _ = self.sql(rule.wrong)
                if (rule.correct.outcome != "MATCH" or rule.wrong.outcome != "MATCH"
                        or rule.correct.fixture.fingerprint != rule.wrong.fixture.fingerprint):
                    raise ValueError("structural discrimination cannot invent a semantic mismatch")
                correct_structure = structural_checks(self.task, correct_sql)
                wrong_structure = structural_checks(self.task, wrong_sql)
                if (correct_structure is None or wrong_structure is None
                        or correct_structure["status"] != "PASS" or wrong_structure["status"] != "FAIL"):
                    raise ValueError("structural control did not discriminate required HAVING")
                self.attribution(declaration.rule_id, rule.correct, rule.wrong, reference, proofs)
                continue
            if rule.disposition == "DOMAIN_CONFORMANCE":
                if (rule.domain_tables is None or rule.invalid_tables is not None or rule.rejection is not None
                        or rule.correct is not None or rule.wrong is not None):
                    raise ValueError("nullable schema requires an executed valid-domain probe, not a rejection waiver")
                table_name, column_name = rule.rule_id.removeprefix("schema:").split(".", 1)
                tables = self.tables(rule.domain_tables)
                if encode(tables) != encode(schema_invalid(self.task, table_name, column_name)):
                    raise ValueError("nullable-domain witness attribution mismatch")
                fixture_fingerprint(self.task, tables)
                if rule.domain_checks != schema_checks(self.task, table_name, column_name):
                    raise ValueError("full declared type/nullability checks missing or inconsistent")
                continue
            if rule.kind == "semantic":
                if rule.domain_tables is not None:
                    raise ValueError("semantic rule cannot claim input-domain conformance")
                if rule.correct is None or rule.wrong is None or rule.invalid_tables is not None or rule.rejection is not None:
                    raise ValueError("semantic rule requires correct and wrong executed witnesses")
                self.pair(rule.correct, rule.wrong)
                self.attribution(declaration.rule_id, rule.correct, rule.wrong, reference, proofs)
                if rule.domain_checks:
                    raise ValueError("semantic rule cannot waive domain checks")
            else:
                if rule.domain_tables is not None:
                    raise ValueError("rejection rule cannot carry a conformance waiver")
                if rule.invalid_tables is None or not rule.rejection or rule.correct is not None or rule.wrong is not None:
                    raise ValueError("input domain requires a retained rejection witness")
                if (self.task.template_id, self.task.template_version) in {
                    ("sql.joins.requested_language_titles", 1),
                    ("sql.retention.renewal_coverage", 1), ("sql.windows.queue_batches", 1),
                } and declaration.proof_key == "exact_schema":
                    # This attributed rejection deliberately contains an extra column.
                    tables = read_json(self.root, rule.invalid_tables)
                else:
                    tables = self.tables(rule.invalid_tables)
                if declaration.proof_key != "schema":
                    proof = proofs[declaration.proof_key]
                    if encode(tables) != encode(proof["witness"]) or rule.domain_checks:
                        raise ValueError("domain witness attribution mismatch")
                    try:
                        if declaration.proof_key == "null_handling":
                            fixture_fingerprint(self.task, tables)
                        else:
                            get_oracle(self.task.template_id, self.task.template_version).fn(self.task.requirements, tables)
                    except Exception as exc:
                        if rule.rejection != str(exc):
                            raise ValueError("domain rejection reason mismatch") from exc
                    else:
                        raise ValueError("domain witness was not rejected")
                    continue
                table_name, column_name = rule.rule_id.removeprefix("schema:").split(".", 1)
                if encode(tables) != encode(schema_invalid(self.task, table_name, column_name)):
                    raise ValueError("schema invalid witness attribution mismatch")
                if rule.domain_checks != schema_checks(self.task, table_name, column_name):
                    raise ValueError("full declared type/nullability checks missing or inconsistent")
                declared = json.loads(rule.declaration_json)
                if declared["nullable"] or not any(r[column_name] is None for r in tables[table_name]):
                    raise ValueError("unsupported domain disposition; keep obligation blocked")
                try:
                    fixture_fingerprint(self.task, tables)
                except Exception as exc:
                    if type(exc).__name__ != "FixtureError" or not isinstance(exc.__cause__, duckdb.ConstraintException):
                        raise ValueError("invalid domain rejection reason") from exc
                    if rule.rejection != str(exc) or f"{table_name}.{column_name}" not in str(exc.__cause__):
                        raise ValueError("domain rejection does not identify the declared column") from exc
                else:
                    raise ValueError("domain witness was not rejected")
        return self.run_count, {"covered_rules": len(public), "semantic_rules": len(self.authority.semantic_rule_ids),
                                "domain_rules": len(self.authority.domain_rule_ids),
                                "structural_rules": len(self.authority.structural_rule_ids)}

    def rule_proofs(self) -> tuple[str, dict[str, Any]]:
        if not self.authority.granular or not self.authority.task_matches_public_contract:
            raise ValueError("granular public instruction behavior coverage unresolved")
        live = Path(__file__).resolve().parents[4]
        for relative in ("scripts/engineering_rule_audit.py", "scripts/phase3_diagnostic.py",
                         "tests/test_business_tasks.py", "tests/test_legacy_adversarial.py"):
            if self.sources.get(relative) != digest(live / relative):
                raise ValueError("public proof attribution source binding missing or stale")
            artifact(self.root, ArtifactRef(path=relative, sha256=self.sources[relative]))
        return public_proofs(self.task)

    def attribution(
        self, rule_id: str, correct: SQLWitness, wrong: SQLWitness,
        reference: str, proofs: dict[str, Any],
    ) -> None:
        declaration = next(r for r in self.authority.rules if r.rule_id == rule_id)
        proof = proofs[declaration.proof_key]
        if (proof.get("outcome") != "UNEXECUTED_RULE_SPEC"
                or artifact(self.root, correct.sql).read_text(encoding="utf-8") != reference
                or artifact(self.root, wrong.sql).read_text(encoding="utf-8") != proof["wrong_sql"]
                or correct.fixture.fingerprint != fixture_fingerprint(self.task, proof["witness"])):
            raise ValueError("SQL witness attribution differs from authoritative clause-specific discriminator")

    def pair(self, correct: SQLWitness, wrong: SQLWitness) -> None:
        self.sql(correct)
        self.sql(wrong)
        if (correct.outcome != "MATCH" or wrong.outcome != "KILLED_WRONG_ANSWER"
                or correct.fixture.fingerprint != wrong.fixture.fingerprint
                or correct.sql.sha256 == wrong.sql.sha256):
            raise ValueError("rule witness is not a valid distinct semantic discriminator")

    def mutations(self, detail: MutationDetail) -> tuple[int, dict[str, Any]]:
        self.authority = public_behavior_map(self.task)
        if sorted(detail.required_rules) != sorted(self.authority.semantic_rule_ids):
            raise ValueError("required mutation rules differ from public authority")
        reference, proofs = self.rule_proofs()
        wrong_ids = set()
        covered = set()
        for mutant in detail.mutants:
            self.pair(mutant.correct, mutant.wrong)
            if mutant.wrong.sql.sha256 in wrong_ids or len(set(mutant.rule_ids)) != len(mutant.rule_ids):
                raise ValueError("duplicate mutant SQL or rule IDs")
            wrong_ids.add(mutant.wrong.sql.sha256)
            if not set(mutant.rule_ids) <= set(self.authority.semantic_rule_ids):
                raise ValueError("invented mutant rule attribution")
            for rule_id in mutant.rule_ids:
                self.attribution(rule_id, mutant.correct, mutant.wrong, reference, proofs)
            covered.update(mutant.rule_ids)
        if len(wrong_ids) < max(3, self.thresholds["minimum_valid_semantic_mutants_per_contract"]) or covered != set(detail.required_rules):
            raise ValueError("insufficient valid semantic mutation coverage")
        if "instruction:declared" in covered:
            raise ValueError("granular public instruction behavior coverage unresolved")
        return self.run_count, {"valid_non_equivalent": len(wrong_ids), "semantic_kills": len(wrong_ids), "rule_coverage": 1}

    def challenges(self, detail: ChallengeDetail) -> tuple[int, dict[str, Any]]:
        for witness in detail.wrong + detail.correct:
            self.sql(witness)
        wrong = {w.sql.sha256 for w in detail.wrong if w.outcome == "KILLED_WRONG_ANSWER"}
        correct = {w.sql.sha256 for w in detail.correct if w.outcome == "MATCH"}
        correct_pairs = {(w.sql.sha256, w.fixture.fingerprint) for w in detail.correct}
        if (len(wrong) != len(detail.wrong) or len(correct_pairs) != len(detail.correct)
                or wrong & correct or len(wrong) < self.thresholds["minimum_wrong_challenges_per_contract"]
                or len(correct) < self.thresholds["minimum_correct_alternatives_per_contract"]):
            raise ValueError("challenge outcomes or distinct alternatives incomplete")
        # Every correct alternative must pass every retained wrong-query witness.
        for wrong_witness in detail.wrong:
            if not all(any(c.sql.sha256 == alternative and c.fixture.fingerprint == wrong_witness.fixture.fingerprint for c in detail.correct)
                       for alternative in correct):
                raise ValueError("correct alternative fixture coverage incomplete")
        return self.run_count, {"witnessed_wrong": len(wrong), "qualified_correct": len(correct), "false_acceptances": 0, "false_rejections": 0}

    def relations(self, detail: RelationsDetail) -> tuple[int, dict[str, Any]]:
        ids = set()
        for relation in detail.relations:
            if relation.relation_id in ids:
                raise ValueError("duplicate relation identity")
            ids.add(relation.relation_id)
            _, before = self.sql(relation.correct_before)
            _, after = self.sql(relation.correct_after)
            transformed, precondition = contract_relation_tables(self.task, before, relation.relation_id)
            if transformed is None or relation.precondition != precondition or fixture_fingerprint(self.task, transformed) != fixture_fingerprint(self.task, after):
                raise ValueError("relation precondition/transform mismatch")
            _, wrong_before = self.sql(relation.wrong_before)
            _, wrong_after = self.sql(relation.wrong_after)
            if (relation.correct_before.outcome != "MATCH" or relation.correct_after.outcome != "MATCH"
                    or relation.wrong_before.outcome != "MATCH" or relation.wrong_after.outcome != "KILLED_WRONG_ANSWER"
                    or relation.correct_before.sql.sha256 != relation.correct_after.sql.sha256
                    or relation.wrong_before.sql.sha256 != relation.wrong_after.sql.sha256
                    or fixture_fingerprint(self.task, wrong_before) != fixture_fingerprint(self.task, before)
                    or fixture_fingerprint(self.task, wrong_after) != fixture_fingerprint(self.task, after)):
                raise ValueError("relation lacks an executed wrong-query discriminator")
        if len(ids) < self.thresholds["minimum_discriminating_relations_per_contract"]:
            raise ValueError("insufficient discriminating relations")
        return self.run_count, {"executed": len(ids), "discriminating": len(ids), "failed": 0}

    def observation_inventory(
        self, cases: Sequence[FuzzObservation], reported: dict[str, dict[str, int]],
    ) -> dict[str, dict[str, int]]:
        """Check per-case claim arithmetic before separately proving fixture observations."""
        _, required, _ = observed_behaviors(self.task.template_id, self.task.template_version,
                                            self.task.tables)
        seen = set()
        counts: dict[str, Counter[str]] = {}
        for case in cases:
            if (case.seed, case.index) in seen:
                raise ValueError("duplicate fuzz case identity")
            seen.add((case.seed, case.index))
            if len(set(case.observed_behaviors)) != len(case.observed_behaviors) or not set(case.observed_behaviors) <= set(required):
                raise ValueError("unknown or duplicate observed fuzz behavior")
            counts.setdefault(str(case.seed), Counter(dict.fromkeys(required, 0))).update(case.observed_behaviors)
        required_cases = {(seed, index) for seed in self.thresholds["hidden_seeds"]
                          for index in range(self.thresholds["random_cases_per_seed"])}
        result = {k: dict(v) for k, v in counts.items()}
        if seen != required_cases or encode(result) != encode(reported):
            raise ValueError("fuzz seed/case counts or observed summaries mismatch")
        return result

    def fuzz(self, detail: FuzzDetail) -> tuple[int, dict[str, Any]]:
        with self:
            return self._fuzz(detail)

    def _fuzz(self, detail: FuzzDetail) -> tuple[int, dict[str, Any]]:
        self.observation_inventory(detail.cases, detail.observed_counts)
        counts: dict[str, Counter[str]] = {}
        seen = set()
        alternatives: set[str] | None = None
        for case in detail.cases:
            if (case.seed, case.index) in seen:
                raise ValueError("duplicate fuzz case identity")
            seen.add((case.seed, case.index))
            tables = self.fixture(case.alternatives[0].fixture)
            generated = observation_fixture(self.task.template_id, self.task.template_version,
                                            case.seed, case.index)
            if case.alternatives[0].fixture.fingerprint != fixture_fingerprint(self.task, generated):
                raise ValueError("fuzz case differs from source-bound seed/index generation")
            policy, required, observed = observed_behaviors(self.task.template_id, self.task.template_version, tables)
            if detail.observation_policy != policy or sorted(case.observed_behaviors) != sorted(observed):
                raise ValueError("fuzz observed behaviors differ from classified fixture content")
            counts.setdefault(str(case.seed), Counter(dict.fromkeys(required, 0))).update(observed)
            sqls = set()
            for witness in case.alternatives:
                self.sql(witness)
                if witness.outcome != "MATCH" or witness.fixture.fingerprint != case.alternatives[0].fixture.fingerprint:
                    raise ValueError("fuzz alternative divergence or fixture mismatch")
                sqls.add(witness.sql.sha256)
            if len(sqls) != len(case.alternatives) or len(sqls) < self.thresholds["minimum_correct_alternatives_per_contract"]:
                raise ValueError("fuzz alternatives not distinct")
            if alternatives is not None and alternatives != sqls:
                raise ValueError("fuzz alternative identity changed between cases")
            alternatives = sqls
        required_cases = {(seed, index) for seed in self.thresholds["hidden_seeds"]
                          for index in range(self.thresholds["random_cases_per_seed"])}
        if seen != required_cases or {k: dict(v) for k, v in counts.items()} != detail.observed_counts:
            raise ValueError("fuzz seed/case counts or observed summaries mismatch")
        if any(min(c.values()) < self.thresholds["mandatory_behavior_cases_per_seed"] for c in counts.values()):
            raise ValueError("fuzz observed behavior coverage incomplete")
        return self.run_count, {"valid_random_cases": len(seen), "observed_coverage_pass": True, "divergences": 0}

    def validate(self, receipt: ReceiptV2) -> None:
        with self:
            self._validate(receipt)

    def _validate(self, receipt: ReceiptV2) -> None:
        category = receipt.category
        if category == "named_tests":
            checks, metrics = self.named_tests(NamedTestsDetail.model_validate(receipt.details))
        elif category == "fixture_diversity":
            checks, metrics = self.fixtures(FixtureDetail.model_validate(receipt.details))
        elif category == "rules":
            checks, metrics = self.rules(RulesDetail.model_validate(receipt.details))
        elif category == "mutation":
            checks, metrics = self.mutations(MutationDetail.model_validate(receipt.details))
        elif category == "challenge":
            checks, metrics = self.challenges(ChallengeDetail.model_validate(receipt.details))
        elif category == "relations":
            checks, metrics = self.relations(RelationsDetail.model_validate(receipt.details))
        else:
            checks, metrics = self.fuzz(FuzzDetail.model_validate(receipt.details))
        if checks != receipt.checks_run or encode(metrics) != encode(receipt.metrics):
            raise ValueError("summary counts differ from retained detailed outcomes")
