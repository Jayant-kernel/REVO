"""Preliminary Stage2 artifact writer; local proof is not runtime qualification.

No Docker, provider, journal or index writes. Category receipts are replay-validated
before emission. Local rules/mutations do not qualify runtime candidate coverage.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from threading import Timer
from typing import Any, Literal

import duckdb
from pydantic import BaseModel, TypeAdapter

from verified_data_factory.generation.models import CandidateSolution, GenerationConfig
from verified_data_factory.sandbox.config import SandboxConfig
from verified_data_factory.sandbox.executor import SandboxExecutor, build_execution_id
from verified_data_factory.sandbox.models import RunResult
from verified_data_factory.sandbox.policy import check_policy
from verified_data_factory.task_engine import generate_task, load_builtin_registry
from verified_data_factory.task_engine.errors import FixtureError
from verified_data_factory.task_engine.fixtures import materialize_duckdb
from verified_data_factory.task_engine.hidden_fixtures import (
    diverse_hidden_tables,
    fixture_fingerprint,
    materialized_fixture_fingerprint,
    materialized_fixture_tables,
)
from verified_data_factory.verification.behavior_authority import public_behavior_map
from verified_data_factory.verification.comparator import compare
from verified_data_factory.verification.metamorphic import contract_relation_tables
from verified_data_factory.verification.oracle_registry import get_oracle
from verified_data_factory.verification.public_rule_proofs import (
    public_proofs,
    schema_checks,
    schema_invalid,
)
from verified_data_factory.verification.qualification.delivery_profiles import PROFILE_IDS
from verified_data_factory.verification.receipt_models import (
    ArtifactRef,
    ChallengeDetail,
    FixtureDetail,
    FixtureWitness,
    FuzzCase,
    FuzzDetail,
    MutationDetail,
    MutationWitness,
    NamedTestsDetail,
    ReceiptV2,
    RelationsDetail,
    RelationWitness,
    RulesDetail,
    RuleWitness,
    SQLWitness,
)
from verified_data_factory.verification.receipt_observations import (
    observation_fixture,
    observed_behaviors,
)
from verified_data_factory.verification.receipt_validation import (
    DetailValidator,
    confined,
    digest,
    required_sources,
    runtime_identity,
    validate_sources,
)

SUPPORTED = {
    *PROFILE_IDS,
    ("sql.dedup.lowest_quote", 1),
    ("sql.funnel.saas_activation_payment", 2),
    ("sql.aggregation.manufacturing_line_scrap", 1),
    ("sql.aggregation.fulfillment_sla_dashboard", 1),
    ("sql.joins.saas_paid_invoices", 1),
    ("sql.subqueries.exists", 2),
    ("sql.joins.logistics_final_leg", 1),
    ("sql.temporal.clinic_weekly_visits", 1),
    ("sql.retention.saas_repeat_payment", 1),
    ("sql.cte.order_line_reconciliation", 1),
    ("sql.windows.media_previous_play", 1),
    ("sql.aggregation.support_sla_breaches", 1),
    ("sql.dedup.education_grade_revisions", 2),
    ("sql.aggregation.warehouse_throughput", 2),
    ("sql.subqueries.education_all_required", 1),
    ("sql.cte.inventory_net_flow", 2),
}
PRODUCER = "scripts/engineering_receipt_artifacts.py"
Tables = dict[str, list[dict[str, Any]]]


class LocalCollector(SandboxExecutor):
    """Use only the real wire collector, without constructing a Docker runner."""

    def __init__(self) -> None:
        self._config = SandboxConfig(
            image="local-stage2-duckdb", config_version="local-stage2-v1",
            timeout_seconds=5, memory_mb=128, cpus=1, max_result_rows=100_000,
            max_result_bytes=10_000_000, max_stdout_bytes=10_000_000,
        )


def catalog_blockers() -> list[dict[str, Any]]:
    """Enumerate latest public versions; support never implies eligibility."""
    registry = load_builtin_registry()
    ids = sorted({t.template_id for t in registry.list()})
    return [
        {"contract_id": tid, "contract_version": registry.get(tid).version,
         "eligible": False,
          "reason": ("complete current receipt bundle and runtime attribution unresolved"
                    if (tid, registry.get(tid).version) in SUPPORTED
                    else "no supported executed producer profile")}
        for tid in ids
    ]


class ArtifactWriter:
    """Append-only retained evidence for an exact supported canonical task.

    Callers must name every additional consumed data/reference input up front.
    All repository Python helpers/tests are conservatively source-locked too.
    Changes during collection deny receipt emission rather than refreshing locks.
    """

    def __init__(
        self, root: Path, destination: str, contract: str, version: int,
        inputs: Sequence[str],
    ) -> None:
        if (contract, version) not in SUPPORTED:
            raise ValueError("unsupported producer contract/version")
        self.root = root.resolve()
        self.destination = confined(self.root, destination)
        if self.destination.name == "qualified-receipts-v9":
            raise ValueError("v9 awaits source stability and independent cold review")
        self.task = generate_task(load_builtin_registry().get(contract, version), 94001)
        self.runtime = runtime_identity()
        self.sources = required_sources()
        for folder in ("scripts", "tests"):
            for path in sorted((self.root / folder).rglob("*.py")):
                self.sources[path.relative_to(self.root).as_posix()] = digest(path)
        for relative in inputs:
            self.sources[relative] = digest(confined(self.root, relative))
        self.thresholds: dict[str, Any] = json.loads(
            confined(self.root, "configs/package_a/engineering-rubric.json").read_text()
        )["thresholds"]
        self.destination.mkdir(parents=True, exist_ok=False)
        self.task_ref = self.write("task.json", self.task.model_dump(mode="json", by_alias=True))
        self.collector = LocalCollector()
        self._sequence = 0

    def write(self, name: str, value: object, *, text: bool = False) -> ArtifactRef:
        path = confined(self.root, self.destination.relative_to(self.root).as_posix() + "/" + name)
        if not path.is_relative_to(self.destination):
            raise ValueError("artifact escapes destination")
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(str(value) if text else json.dumps(value, default=str, sort_keys=True))
        return ArtifactRef(path=path.relative_to(self.root).as_posix(), sha256=digest(path))

    def input_sql(self, relative: str) -> str:
        path = confined(self.root, relative)
        if self.sources.get(relative) != digest(path):
            raise ValueError("SQL input absent from stable source closure")
        return path.read_text(encoding="utf-8")

    def fixture(
        self, tables: Tables, origin: Literal["original", "seed", "targeted"] = "targeted",
        seed: int | None = None,
    ) -> FixtureWitness:
        # Bind the oracle to actual typed DB cells, not raw JSON spellings.
        connection = materialize_duckdb(self.task.schema_, tables)
        try:
            canonical = materialized_fixture_tables(self.task, connection)
            fingerprint = materialized_fixture_fingerprint(self.task, connection)
        finally:
            connection.close()
        self._sequence += 1
        return FixtureWitness(
            tables=self.write(f"fixture-{self._sequence}.json", canonical),
            fingerprint=fingerprint,
            expected=get_oracle(self.task.template_id, self.task.template_version).fn(
                self.task.requirements, canonical,
            ), origin=origin, seed=seed,
        )

    def sql(self, sql: str, fixture: FixtureWitness) -> SQLWitness:
        return self._sql(sql, fixture, None)

    def sql_many(self, alternatives: Sequence[str], fixture: FixtureWitness) -> list[SQLWitness]:
        """One bounded connection for one fixture; every alternative actually runs."""
        path = confined(self.root, fixture.tables.path)
        if digest(path) != fixture.tables.sha256:
            raise ValueError("stale fixture artifact")
        connection = materialize_duckdb(self.task.schema_, json.loads(path.read_text()))
        try:
            return [self._sql(sql, fixture, connection) for sql in alternatives]
        finally:
            connection.close()

    def _sql(
        self, sql: str, fixture: FixtureWitness, shared: duckdb.DuckDBPyConnection | None,
    ) -> SQLWitness:
        if not check_policy(sql).allowed:
            raise ValueError("SQL policy rejected; not a semantic witness")
        self._sequence += 1
        name = f"run-{self._sequence}"
        now = datetime.now(UTC).isoformat()
        candidate = CandidateSolution(
            candidate_id=f"{self.task.task_id}.local-{hashlib.sha256(sql.encode()).hexdigest()}",
            task_id=self.task.task_id, model="retained-local-sql", model_revision="1",
            prompt_version="none-manual-sql", generation_schema_version="1.0",
            provider="local", endpoint_id="none", candidate_index=0,
            raw_response=sql, candidate_sql=sql, generation_config=GenerationConfig(),
            generation_timestamp=now, generation_duration_ms=0,
            finish_reason="manual SQL input; no model call",
        )
        tables: Tables = json.loads(confined(self.root, fixture.tables.path).read_text())
        if digest(confined(self.root, fixture.tables.path)) != fixture.tables.sha256:
            raise ValueError("stale fixture artifact")
        started = datetime.now(UTC).isoformat()
        connection = shared if shared is not None else materialize_duckdb(self.task.schema_, tables)
        timer = Timer(self.collector.config.timeout_seconds, connection.interrupt)
        transaction_started = False
        try:
            connection.execute("SET enable_external_access = false")
            connection.execute("SET threads = 1")
            connection.execute("SET memory_limit = '128MB'")
            statements = connection.extract_statements(sql)
            if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
                raise ValueError("SQL policy rejected; not a semantic witness")
            connection.execute("BEGIN TRANSACTION")
            transaction_started = True
            timer.start()
            cursor = connection.execute(sql)
            rows = [list(row) for row in cursor.fetchmany(100_001)]
            payload = {
                "columns": [{"name": c[0], "type": str(c[1])} for c in cursor.description],
                "rows": rows, "truncated": len(rows) > 100_000,
                "duckdb_version": duckdb.__version__,
            }
        except duckdb.Error as exc:
            payload = {"status": "error", "error": {"message": str(exc)},
                       "duckdb_version": duckdb.__version__}
        finally:
            timer.cancel()
            if timer.ident is not None:
                timer.join()
            try:
                if transaction_started:
                    connection.execute("ROLLBACK")
            finally:
                if shared is None:
                    connection.close()
        execution = self.collector._collect(
            {"execution_id": build_execution_id(candidate.candidate_id, started),
             "task_id": self.task.task_id, "candidate_id": candidate.candidate_id,
             "resource_limits": self.collector.config.resource_limits(),
             "sandbox_image": self.collector.config.image,
             "sandbox_config_version": self.collector.config.config_version,
             "started_at": started}, started,
            RunResult(exit_code=0, stdout=json.dumps(payload, default=str).encode(), stderr=b""),
        )
        sql_ref = self.write(name + ".sql", sql, text=True)
        candidate_ref = self.write(name + "-candidate.json", candidate.model_dump(mode="json"))
        execution_ref = self.write(name + "-execution.json", execution.model_dump(mode="json"))
        data = execution.result_data
        if (execution.status != "SUCCEEDED" or data is None or data.truncated
                or execution.stdout_truncated or execution.stderr_truncated):
            raise ValueError(f"retained {execution.status} execution is not semantic evidence")
        comparison = compare(fixture.expected, [c.name for c in data.columns], data.rows,
                             column_types=[c.type for c in data.columns])
        return SQLWitness(
            sql=sql_ref, candidate=candidate_ref, execution=execution_ref, fixture=fixture,
            comparison=comparison, outcome="MATCH" if comparison.match else "KILLED_WRONG_ANSWER",
        )

    def diversity(self) -> FixtureDetail:
        return FixtureDetail(fixtures=[
            self.fixture(self.task.tables, "original"),
            *(self.fixture(diverse_hidden_tables(self.task, seed, index), "seed", seed)
              for index, seed in enumerate(self.thresholds["hidden_seeds"], 1)),
        ])

    def rules(self) -> RulesDetail:
        authority = public_behavior_map(self.task)
        reference, proofs = public_proofs(self.task)
        rules = []
        pairs = {}
        for declaration in authority.rules:
            fields: dict[str, Any] = {
                "rule_id": declaration.rule_id, "kind": declaration.kind,
                "declaration_json": declaration.declaration_json,
                "source_clause": declaration.source_clause,
            }
            if declaration.kind in {"semantic", "structural"}:
                proof = proofs[declaration.proof_key]
                if declaration.proof_key not in pairs:
                    fixture = self.fixture(proof["witness"])
                    pairs[declaration.proof_key] = self.sql_many([reference, proof["wrong_sql"]], fixture)
                correct, wrong = pairs[declaration.proof_key]
                rules.append(RuleWitness(**fields, disposition="SEMANTIC_DISCRIMINATOR" if declaration.kind == "semantic" else "STRUCTURAL_DISCRIMINATOR",
                                         correct=correct, wrong=wrong))
            else:
                checks = {}
                if declaration.proof_key == "schema":
                    table, column = declaration.rule_id.removeprefix("schema:").split(".")
                    invalid = schema_invalid(self.task, table, column)
                    checks = schema_checks(self.task, table, column)
                    if json.loads(declaration.declaration_json)["nullable"]:
                        fixture_fingerprint(self.task, invalid)
                        self._sequence += 1
                        rules.append(RuleWitness(**fields, disposition="DOMAIN_CONFORMANCE",
                            domain_tables=self.write(f"domain-{self._sequence}.json", invalid), domain_checks=checks))
                        continue
                else:
                    invalid = proofs[declaration.proof_key]["witness"]
                try:
                    if declaration.proof_key in {"schema", "null_handling"}:
                        fixture_fingerprint(self.task, invalid)
                    else:
                        get_oracle(self.task.template_id, self.task.template_version).fn(self.task.requirements, invalid)
                except (FixtureError, ValueError) as exc:
                    reason = str(exc)
                else:
                    raise ValueError("invalid public domain witness not rejected")
                self._sequence += 1
                rules.append(RuleWitness(**fields, disposition="DOMAIN_REJECTION",
                                         invalid_tables=self.write(f"invalid-{self._sequence}.json", invalid),
                                         rejection=reason, domain_checks=checks))
        return RulesDetail(rules=rules)

    def mutations(self, rules: RulesDetail) -> MutationDetail:
        groups = {}
        for rule in rules.rules:
            if rule.kind == "semantic":
                if rule.correct is None or rule.wrong is None:
                    raise ValueError("semantic mutation requires executed witnesses")
                key = (rule.wrong.sql.sha256, rule.correct.fixture.fingerprint)
                if key not in groups:
                    groups[key] = MutationWitness(rule_ids=[rule.rule_id], correct=rule.correct, wrong=rule.wrong)
                else:
                    groups[key].rule_ids.append(rule.rule_id)
        # One canonical mutant may cover multiple clauses on different fixtures.
        # Profiles sharing SQL also share their targeted fixture in these versions.
        return MutationDetail(required_rules=list(public_behavior_map(self.task).semantic_rule_ids),
                              mutants=list(groups.values()))

    def challenges(
        self, wrong: Sequence[tuple[str, Tables]], alternatives: Sequence[str],
    ) -> ChallengeDetail:
        fixtures: dict[str, FixtureWitness] = {}
        wrong_runs = []
        for sql, tables in wrong:
            fingerprint = fixture_fingerprint(self.task, tables)
            if fingerprint not in fixtures:
                fixtures[fingerprint] = self.fixture(tables)
            wrong_runs.append(self.sql(sql, fixtures[fingerprint]))
        return ChallengeDetail(
            wrong=wrong_runs,
            correct=[self.sql(sql, fixture) for fixture in fixtures.values() for sql in alternatives],
        )

    def relations(
        self, correct: str, discriminators: Sequence[tuple[str, str, Tables]],
    ) -> RelationsDetail:
        witnesses = []
        for relation_id, wrong, tables in discriminators:
            transformed, precondition = contract_relation_tables(self.task, tables, relation_id)
            if transformed is None:
                raise ValueError("relation precondition not met")
            before, after = self.fixture(tables), self.fixture(transformed)
            witnesses.append(RelationWitness(
                relation_id=relation_id, relation_version=2, precondition=precondition,
                correct_before=self.sql(correct, before), correct_after=self.sql(correct, after),
                wrong_before=self.sql(wrong, before), wrong_after=self.sql(wrong, after),
            ))
        return RelationsDetail(relations=witnesses)

    def fuzz(self, alternatives: Sequence[str]) -> FuzzDetail:
        # Reject unsupported wire policy before spending 2700 SQL executions.
        TypeAdapter(FuzzDetail.model_fields["observation_policy"].annotation).validate_python(
            observed_behaviors(self.task.template_id, self.task.template_version, self.task.tables)[0]
        )
        cases = []
        counts: dict[str, dict[str, int]] = {}
        policy = ""
        for seed in self.thresholds["hidden_seeds"]:
            counter: Counter[str] = Counter()
            for index in range(self.thresholds["random_cases_per_seed"]):
                fixture = self.fixture(observation_fixture(
                    self.task.template_id, self.task.template_version, seed, index,
                ))
                tables = json.loads(confined(self.root, fixture.tables.path).read_text())
                policy, required, observed = observed_behaviors(
                    self.task.template_id, self.task.template_version, tables,
                )
                for behavior in required:
                    counter.setdefault(behavior, 0)
                counter.update(observed)
                cases.append(FuzzCase(seed=seed, index=index, observed_behaviors=sorted(observed),
                                      alternatives=self.sql_many(alternatives, fixture)))
            counts[str(seed)] = dict(counter)
        return FuzzDetail.model_validate({"observation_policy": policy, "cases": cases,
                                         "observed_counts": counts})

    def named_tests(self, nodes: Sequence[str]) -> NamedTestsDetail:
        report = self.destination / "tests.xml"
        if report.exists():
            raise ValueError("named report already exists")
        command = [sys.executable, "-m", "pytest", *nodes, "-q",
                   "-o", "junit_family=xunit1", "--junitxml", str(report)]
        result = subprocess.run(command, cwd=self.root, capture_output=True, text=True, check=False)
        self.write("tests.log", result.stdout + result.stderr, text=True)
        if result.returncode:
            raise ValueError("named tests failed; retained log is not passing evidence")
        outcomes = {}
        for case in ET.parse(report).iter("testcase"):
            properties = {p.attrib["name"]: p.attrib["value"]
                          for p in case.findall("properties/property")}
            if (properties.get("contract_id") == self.task.template_id
                    and properties.get("contract_version") == str(self.task.template_version)):
                node = properties.get("node_id", "")
                if node in outcomes:
                    raise ValueError("duplicate attributed test node")
                outcomes[node] = next((tag for tag in ("error", "failed", "skipped")
                                       if case.find("failure" if tag == "failed" else tag)
                                       is not None), "passed")
        return NamedTestsDetail.model_validate({
            "report": ArtifactRef(path=report.relative_to(self.root).as_posix(), sha256=digest(report)),
            "nodes": outcomes, "command": command, "exit_code": result.returncode,
        })

    def receipt(self, category: str, detail: BaseModel) -> ArtifactRef:
        authority = public_behavior_map(self.task)
        checker = DetailValidator(self.root, self.task, authority, self.sources, self.thresholds)
        if category == "fixture_diversity" and isinstance(detail, FixtureDetail):
            checks, metrics = checker.fixtures(detail)
        elif category == "challenge" and isinstance(detail, ChallengeDetail):
            checks, metrics = checker.challenges(detail)
        elif category == "relations" and isinstance(detail, RelationsDetail):
            checks, metrics = checker.relations(detail)
        elif category == "fuzz" and isinstance(detail, FuzzDetail):
            checks, metrics = checker.fuzz(detail)
        elif category == "named_tests" and isinstance(detail, NamedTestsDetail):
            checks, metrics = checker.named_tests(detail)
        elif category == "rules" and isinstance(detail, RulesDetail):
            checks, metrics = checker.rules(detail)
        elif category == "mutation" and isinstance(detail, MutationDetail):
            checks, metrics = checker.mutations(detail)
        else:
            raise ValueError("category not supported by preliminary producer")
        envelope = ReceiptV2.model_validate({
            "schema_version": 2, "evidence_id": self.destination.relative_to(self.root).as_posix() + "-" + category,
            "category": category,
            "producer": PRODUCER, "created_at": datetime.now(UTC),
            "contract_id": self.task.template_id, "contract_version": self.task.template_version,
            "task": self.task_ref, "oracle_version": get_oracle(
                self.task.template_id, self.task.template_version,
            ).oracle_version, "behavior_map_sha256": authority.declaration_sha256,
            "source_hashes": self.sources, "checks_run": checks, "execution_failures": 0,
            "runtime": self.runtime,
            "unresolved_findings": [], "metrics": metrics, "details": detail.model_dump(mode="json"),
        })
        validate_sources(self.root, envelope)
        # The fresh category checker above already replayed every retained detail.
        # Independent receipt consumers still create their own validation scope.
        return self.write(category + "-receipt.json", envelope.model_dump(mode="json"))
