"""Verification data models (Phase 4).

Verdicts: PASS (proven correct), FAIL (proven violating), INCONCLUSIVE
(infrastructure could not establish correctness). There is deliberately
no bare ``FAILED``: candidate faults and verifier faults are distinct.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

VERIFICATION_CONFIG_VERSION = "1.0"

Verdict = Literal["PASS", "FAIL", "INCONCLUSIVE"]
Strength = Literal["STRONG", "WEAK", "UNKNOWN"]
MutantClassification = Literal[
    "SEMANTIC_KILL",
    "SURVIVED",
    "INVALID_MUTANT",
    "INFRA_INCONCLUSIVE",
    "UNKNOWN",
]

VerificationFailureCode = Literal[
    "RESULT_MISMATCH",
    "HIDDEN_MISMATCH",
    "PROPERTY_FAILED",
    "METAMORPHIC_FAILED",
    "EXECUTION_FAILED",
    "POLICY_REJECTED",
    "TRUNCATED_RESULT",
    "ORACLE_ERROR",
    "ORACLE_UNKNOWN",
    "SANDBOX_INFRA_ERROR",
    "WEAK_SUITE",
    "INVALID_INPUT",
]

OrderType = Literal["unordered", "ordered"]


class OrderSpec(BaseModel):
    """How result order is judged. ``keys`` are (column, direction) pairs."""

    model_config = {"frozen": True}

    type: OrderType = "unordered"
    keys: list[tuple[str, Literal["asc", "desc"]]] = Field(default_factory=list)


class ComparisonPolicy(BaseModel):
    model_config = {"frozen": True}

    float_abs_tol: float = Field(default=1e-9, ge=0)
    float_rel_tol: float = Field(default=1e-7, ge=0)
    column_names_case_sensitive: bool = False
    column_order_strict: bool = True


class ExpectedResult(BaseModel):
    """Independent oracle output: the behavior the task specification demands."""

    model_config = {"frozen": True}

    columns: list[str] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    order: OrderSpec = Field(default_factory=OrderSpec)


class RowDifference(BaseModel):
    model_config = {"frozen": True}

    index: int
    expected: list[Any] = Field(default_factory=list)
    actual: list[Any] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    model_config = {"frozen": True}

    match: bool
    expected_rows: int = Field(ge=0)
    actual_rows: int = Field(ge=0)
    expected_columns: list[str] = Field(default_factory=list)
    actual_columns: list[str] = Field(default_factory=list)
    order_spec: OrderSpec = Field(default_factory=OrderSpec)
    policy: ComparisonPolicy = Field(default_factory=ComparisonPolicy)
    differences: list[RowDifference] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class OracleOutcome(BaseModel):
    model_config = {"frozen": True}

    ok: bool
    strategy: str = ""
    oracle_version: int = 0
    runtime_ms: int = Field(ge=0, default=0)
    expected: ExpectedResult | None = None
    error: str | None = None


class HiddenCaseOutcome(BaseModel):
    model_config = {"frozen": True}

    index: int = Field(ge=0)
    seed: int = Field(ge=0)
    status: Verdict = "INCONCLUSIVE"
    failure_code: VerificationFailureCode | None = None
    detail: str = ""


class HiddenTestResult(BaseModel):
    model_config = {"frozen": True}

    total: int = Field(ge=0, default=0)
    passed: int = Field(ge=0, default=0)
    failed: int = Field(ge=0, default=0)
    inconclusive: int = Field(ge=0, default=0)
    seeds: list[int] = Field(default_factory=list)
    cases: list[HiddenCaseOutcome] = Field(default_factory=list)


class PropertyOutcome(BaseModel):
    model_config = {"frozen": True}

    property_id: str = Field(min_length=1)
    property_version: int = Field(ge=1, default=1)
    applicable: bool = True
    passed: bool = False
    detail: str = ""


class PropertyResult(BaseModel):
    model_config = {"frozen": True}

    applicable: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    outcomes: list[PropertyOutcome] = Field(default_factory=list)


class MetamorphicOutcome(BaseModel):
    model_config = {"frozen": True}

    relation_id: str = Field(min_length=1)
    relation_version: int = Field(ge=1, default=1)
    applicable: bool = True
    passed: bool = False
    detail: str = ""


class MetamorphicResult(BaseModel):
    model_config = {"frozen": True}

    applicable: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    outcomes: list[MetamorphicOutcome] = Field(default_factory=list)


class MutantDetail(BaseModel):
    model_config = {"frozen": True}

    operator: str = Field(min_length=1)
    caught: bool
    classification: MutantClassification = "UNKNOWN"
    reason: str = ""


class MutationResult(BaseModel):
    model_config = {"frozen": True}

    applicable: int = Field(ge=0, default=0)
    run: int = Field(ge=0, default=0)
    caught: int = Field(ge=0, default=0)
    semantic_kills: int = Field(ge=0, default=0)
    survived: int = Field(ge=0, default=0)
    invalid: int = Field(ge=0, default=0)
    inconclusive: int = Field(ge=0, default=0)
    mutation_score: float | None = None
    min_score: float = Field(default=0.9, ge=0, le=1)
    details: list[MutantDetail] = Field(default_factory=list)


class PerformanceOutcome(BaseModel):
    model_config = {"frozen": True}

    duration_ms: int | None = None
    warn_after_ms: int | None = None
    within_budget: bool | None = None
    note: str = ""


class VerificationConfig(BaseModel):
    model_config = {"frozen": True}

    hidden_cases: int = Field(default=3, ge=0, le=50)
    properties_enabled: bool = True
    metamorphic_enabled: bool = True
    mutation_enabled: bool = True
    max_mutations: int = Field(default=20, ge=0, le=100)
    mutation_min_score: float = Field(default=0.9, ge=0, le=1)
    performance_enabled: bool = True
    performance_warn_after_ms: int | None = None
    comparison: ComparisonPolicy = Field(default_factory=ComparisonPolicy)
    config_version: str = Field(default=VERIFICATION_CONFIG_VERSION, min_length=1)


class VerificationResult(BaseModel):
    model_config = {"frozen": True, "populate_by_name": True}

    verification_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    execution_id: str | None = None
    verdict: Verdict
    failure_code: VerificationFailureCode | None = None
    summary: str = Field(default="")
    verification_strength: Strength = "UNKNOWN"
    oracle: OracleOutcome | None = None
    comparison: ComparisonResult | None = None
    hidden: HiddenTestResult | None = None
    properties: PropertyResult | None = None
    metamorphic: MetamorphicResult | None = None
    mutation: MutationResult | None = None
    performance: PerformanceOutcome | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    verification_config_version: str = Field(min_length=1)
    oracle_version: int = Field(ge=0, default=0)
    started_at: str = Field(min_length=1)
    finished_at: str = Field(min_length=1)
