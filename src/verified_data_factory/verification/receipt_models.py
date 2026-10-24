"""Schema v2 retained evidence; no numeric summary establishes a passing check."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .models import COMPARISON_VERSION, ComparisonResult, ExpectedResult


class DetailModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArtifactRef(DetailModel):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ReceiptV2(DetailModel):
    schema_version: Literal[2]
    evidence_id: str = Field(min_length=1)
    producer: str = Field(min_length=1)
    created_at: datetime
    contract_id: str = Field(min_length=1)
    contract_version: int = Field(ge=1, strict=True)
    category: Literal[
        "rules", "named_tests", "relations", "mutation", "challenge", "fixture_diversity", "fuzz"
    ]
    task: ArtifactRef
    oracle_version: int = Field(ge=1, strict=True)
    comparison_version: str = COMPARISON_VERSION
    behavior_map_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_hashes: dict[str, str]
    runtime: dict[str, str]
    checks_run: int = Field(ge=1, strict=True)
    execution_failures: int = Field(ge=0, le=0, strict=True)
    unresolved_findings: list[str]
    metrics: dict[str, Any]
    details: dict[str, Any]


class FixtureWitness(DetailModel):
    tables: ArtifactRef
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected: ExpectedResult
    origin: Literal["original", "seed", "targeted"]
    seed: int | None = Field(default=None, ge=0, strict=True)


class SQLWitness(DetailModel):
    sql: ArtifactRef
    candidate: ArtifactRef
    execution: ArtifactRef
    fixture: FixtureWitness
    comparison: ComparisonResult
    outcome: Literal["MATCH", "KILLED_WRONG_ANSWER"]


class RuleWitness(DetailModel):
    rule_id: str
    kind: Literal["semantic", "input_domain", "structural"]
    declaration_json: str
    disposition: Literal["SEMANTIC_DISCRIMINATOR", "STRUCTURAL_DISCRIMINATOR", "DOMAIN_REJECTION", "DOMAIN_CONFORMANCE", "BLOCKED"]
    blocked_reason: str = ""
    correct: SQLWitness | None = None
    wrong: SQLWitness | None = None
    invalid_tables: ArtifactRef | None = None
    domain_tables: ArtifactRef | None = None
    rejection: str | None = None
    source_clause: str = ""
    domain_checks: dict[str, Any] = Field(default_factory=dict)


class RulesDetail(DetailModel):
    rules: list[RuleWitness] = Field(min_length=1)


class NamedTestsDetail(DetailModel):
    report: ArtifactRef
    nodes: dict[str, Literal["passed", "failed", "error", "skipped"]]
    command: list[str] = Field(min_length=1)
    exit_code: int = Field(ge=0, le=0, strict=True)


class MutationWitness(DetailModel):
    rule_ids: list[str] = Field(min_length=1)
    correct: SQLWitness
    wrong: SQLWitness


class MutationDetail(DetailModel):
    required_rules: list[str] = Field(min_length=1)
    mutants: list[MutationWitness] = Field(min_length=3)


class ChallengeDetail(DetailModel):
    wrong: list[SQLWitness] = Field(min_length=20)
    correct: list[SQLWitness] = Field(min_length=3)


class FixtureDetail(DetailModel):
    fixtures: list[FixtureWitness] = Field(min_length=4)


class RelationWitness(DetailModel):
    relation_id: str
    relation_version: Literal[2]
    precondition: str = Field(min_length=1)
    correct_before: SQLWitness
    correct_after: SQLWitness
    wrong_before: SQLWitness
    wrong_after: SQLWitness


class RelationsDetail(DetailModel):
    relations: list[RelationWitness] = Field(min_length=2)


class FuzzObservation(DetailModel):
    seed: int = Field(ge=0, strict=True)
    index: int = Field(ge=0, strict=True)
    observed_behaviors: list[str]


class FuzzCase(FuzzObservation):
    alternatives: list[SQLWitness] = Field(min_length=3)


class FuzzDetail(DetailModel):
    observation_policy: Literal["scrap-observed-v1", "saas-observed-v1", "sla-observed-v1",
                                 "paid-invoices-observed-v1", "exists-observed-v1",
                                 "final-leg-observed-v1", "weekly-visits-observed-v1",
                                 "repeat-payment-observed-v1", "reconciliation-observed-v1",
                                 "previous-play-observed-v1", "support-breaches-observed-v1",
                                  "grade-immutable-observed-v2", "throughput-observed-v2",
                                   "required-courses-observed-v1", "inventory-net-flow-observed-v2",
                                   "lowest-quote-observed-v1", "language-titles-observed-v1",
                                    "pareto-shipping-observed-v1", "renewal-coverage-observed-v1",
                                    "queue-batches-observed-v1"]
    cases: list[FuzzCase] = Field(min_length=900)
    observed_counts: dict[str, dict[str, StrictInt]]
