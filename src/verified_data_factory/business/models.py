"""Business-layer models (Phase 8).

Authority boundaries: Phase 4 owns correctness, Phase 5 owns Golden
qualification, Phase 6 owns provenance, Phase 7 owns product packaging.
These models own model-value measurement, customer validation,
economics, and GTM evidence — nothing else. Every persisted structure
carries ``schema_version``. All models are frozen; measurement outcomes
are data, never exceptions.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

BUSINESS_ENGINE_VERSION = "1.0"
BUSINESS_SCHEMA_VERSION = "1.0"

EvidenceStatus = Literal[
    "OBSERVED", "MEASURED", "USER_REPORTED", "ASSUMED", "UNKNOWN", "TEST_FIXTURE"
]
ClaimType = Literal["TECHNICAL", "QUALITY", "PERFORMANCE", "CUSTOMER", "ECONOMIC", "MARKET"]
Maturity = Literal[
    "HYPOTHESIS", "OBSERVED", "MEASURED", "REPLICATED", "CUSTOMER_VALIDATED", "COMMERCIALIZED"
]
PrivacyLevel = Literal["PUBLIC", "INTERNAL", "PRIVATE"]
AdaptationMethod = Literal[
    "SFT", "LORA", "FULL_FINE_TUNE", "RETRIEVAL_CONTEXT", "PROMPT_ONLY", "OTHER", "NONE"
]
BaselineSource = Literal[
    "PUBLIC_SYNTHETIC", "INTERNAL", "GENERIC_SYNTHETIC", "HUMAN_AUTHORED", "NONE"
]
FeedbackClass = Literal[
    "PROBLEM_CONFIRMED",
    "PROBLEM_NOT_CONFIRMED",
    "PRODUCT_USEFUL",
    "PRODUCT_NOT_USEFUL",
    "QUALITY_CONCERN",
    "PRICE_CONCERN",
    "INTEGRATION_CONCERN",
    "FORMAT_CONCERN",
    "COMPLIANCE_CONCERN",
    "NO_DECISION",
]
WillingnessSignal = Literal[
    "INTEREST",
    "MEETING_REQUEST",
    "PILOT_ACCEPTED",
    "DATASET_TESTED",
    "PURCHASE_INTENT",
    "PAID_PILOT",
    "PAID_PURCHASE",
    "REPEAT_PURCHASE",
]
PilotStatus = Literal["PLANNED", "ACTIVE", "COMPLETED", "PAUSED", "CANCELLED"]
FailureMode = Literal[
    "NO_PERFORMANCE_GAIN",
    "BENCHMARK_CONTAMINATION",
    "TRAINING_FAILURE",
    "EVALUATION_FAILURE",
    "MODEL_TIMEOUT",
    "DATA_FORMAT_FAILURE",
    "INTEGRATION_FAILURE",
    "CUSTOMER_DID_NOT_TEST",
    "CUSTOMER_REJECTED",
    "PRICE_OBJECTION",
    "COMPLIANCE_BLOCKER",
    "INSUFFICIENT_DATA",
]
HypothesisVerdict = Literal[
    "HYPOTHESIS_SUPPORTED", "HYPOTHESIS_NOT_SUPPORTED", "INSUFFICIENT_EVIDENCE"
]
ClaimVerdict = Literal["CLAIM_SUPPORTED", "CLAIM_UNSUPPORTED"]

FAILURE_MODE_VALUES: tuple[str, ...] = (
    "NO_PERFORMANCE_GAIN",
    "BENCHMARK_CONTAMINATION",
    "TRAINING_FAILURE",
    "EVALUATION_FAILURE",
    "MODEL_TIMEOUT",
    "DATA_FORMAT_FAILURE",
    "INTEGRATION_FAILURE",
    "CUSTOMER_DID_NOT_TEST",
    "CUSTOMER_REJECTED",
    "PRICE_OBJECTION",
    "COMPLIANCE_BLOCKER",
    "INSUFFICIENT_DATA",
)
OfferStatus = Literal["EXPERIMENTAL", "PILOT", "BETA", "PRODUCTION_CANDIDATE"]
PricingUnit = Literal["DATASET", "RECORD", "RECORDS_1K", "SUBSCRIPTION", "EVALUATION_RUN"]
ValueBasis = Literal["ASSUMED", "MEASURED"]
RunStatus = Literal["COMPLETED", "FAILED"]
StatMethod = Literal["MCNEMAR_EXACT", "WILSON", "NONE", "INSUFFICIENT_DATA"]
CommercialStatus = Literal["PLANNED", "RUNNING", "COMPLETED", "CANCELLED"]
CriterionOutcome = Literal["MET", "UNMET", "UNEVALUATED"]

# Willingness ladder in increasing commitment order (§43). Signals are
# observations; a higher rung is never inferred from a lower one.
WILLINGNESS_ORDER: tuple[WillingnessSignal, ...] = (
    "INTEREST",
    "MEETING_REQUEST",
    "PILOT_ACCEPTED",
    "DATASET_TESTED",
    "PURCHASE_INTENT",
    "PAID_PILOT",
    "PAID_PURCHASE",
    "REPEAT_PURCHASE",
)

# Purchase-level signals require an explicit evidence reference (§43).
PURCHASE_LEVEL_SIGNALS: frozenset[WillingnessSignal] = frozenset(
    {"PURCHASE_INTENT", "PAID_PILOT", "PAID_PURCHASE", "REPEAT_PURCHASE"}
)

FUNNEL_STAGES: tuple[str, ...] = (
    "qualified_leads",
    "discovery_conversations",
    "technical_evaluations",
    "pilot_requests",
    "pilot_starts",
    "pilot_completions",
    "paid_pilots",
    "paid_customers",
    "repeat_customers",
)


class BusinessEvidence(BaseModel):
    """One classified evidence record (§6). Status is load-bearing."""

    model_config = {"frozen": True}

    evidence_id: str = Field(min_length=1)
    evidence_type: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    value: float | None = None
    unit: str = ""
    source: str = Field(min_length=1)
    source_reference: str = ""
    measurement_method: str = ""
    population: str = ""
    dataset_release_id: str | None = None
    benchmark_id: str | None = None
    experiment_id: str | None = None
    timestamp: str = ""
    status: EvidenceStatus = "UNKNOWN"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str = ""
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class BusinessClaim(BaseModel):
    """A checkable business claim linked to evidence ids (§7)."""

    model_config = {"frozen": True}

    claim_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    claim_type: ClaimType = "TECHNICAL"
    evidence_ids: list[str] = Field(default_factory=list)
    status: Maturity = "HYPOTHESIS"
    last_validated: str = ""
    metric: str | None = None
    asserted_baseline: float | None = None
    asserted_treatment: float | None = None
    asserted_delta_pp: float | None = None
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class BenchmarkItem(BaseModel):
    """One benchmark member. ``expected_sql`` is private by default."""

    model_config = {"frozen": True}

    record_id: str = Field(min_length=1)
    family: str = Field(min_length=1)
    edge_cases: list[str] = Field(default_factory=list)
    template_id: str | None = None
    semantic_group: str | None = None
    exact_group: str | None = None
    structural_group: str | None = None
    expected_sql: str | None = None


class BenchmarkDefinition(BaseModel):
    """Versioned benchmark header; members live alongside, never public (§9–§10)."""

    model_config = {"frozen": True}

    benchmark_id: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    dataset_release_id: str | None = None
    split: str = Field(min_length=1)
    task_families: list[str] = Field(min_length=1)
    record_ids: list[str] = Field(min_length=1)
    fingerprint: str = Field(min_length=1)
    evaluation_policy: str = Field(min_length=1)
    scoring_policy: str = Field(min_length=1)
    privacy_level: PrivacyLevel = "PRIVATE"
    frozen: bool = False
    created_at: str = ""
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class ContaminationCheck(BaseModel):
    """Benchmark-vs-training overlap report (§11). Clean means no overlap found."""

    model_config = {"frozen": True}

    benchmark_id: str = Field(min_length=1)
    exact_overlap: list[str] = Field(default_factory=list)
    structural_overlap: list[str] = Field(default_factory=list)
    semantic_overlap: list[str] = Field(default_factory=list)
    template_overlap: list[str] = Field(default_factory=list)
    membership_leakage: list[str] = Field(default_factory=list)
    is_clean: bool = False
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class BaselineDataset(BaseModel):
    """Ablation reference recorded as metadata; contents never copied (§22)."""

    model_config = {"frozen": True}

    baseline_dataset_id: str = Field(min_length=1)
    baseline_dataset_version: str = ""
    baseline_dataset_source: str = Field(min_length=1)
    source_type: BaselineSource = "NONE"
    license_identifier: str | None = None
    observed_attributes: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class PredictionOutcome(BaseModel):
    """One externally evaluated benchmark prediction (§15, §72).

    Correctness comes from the owner's harness (ideally Phase 3/4
    infrastructure or equivalent). Phase 8 aggregates; it never judges.
    """

    model_config = {"frozen": True}

    record_id: str = Field(min_length=1)
    correct: bool
    family: str = Field(min_length=1)
    edge_cases: list[str] = Field(default_factory=list)
    latency_ms: float | None = Field(default=None, ge=0.0)
    error_type: str | None = None


class BenchmarkScores(BaseModel):
    """Aggregated benchmark scores; unknown metrics stay None, never zero (§73)."""

    model_config = {"frozen": True}

    n: int = Field(ge=0)
    execution_accuracy: float = Field(ge=0.0, le=1.0)
    benchmark_pass_rate: float = Field(ge=0.0, le=1.0)
    family_scores: dict[str, float] = Field(default_factory=dict)
    family_counts: dict[str, int] = Field(default_factory=dict)
    edge_scores: dict[str, float] = Field(default_factory=dict)
    edge_counts: dict[str, int] = Field(default_factory=dict)
    parse_rate: float | None = None
    execution_success_rate: float | None = None
    invalid_sql_rate: float | None = None
    timeout_rate: float | None = None
    avg_latency_ms: float | None = None
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class BaselineRun(BaseModel):
    """A recorded baseline evaluation (§12)."""

    model_config = {"frozen": True}

    run_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_revision: str = ""
    provider: str = ""
    generation_config: dict[str, Any] = Field(default_factory=dict)
    dataset_context: str = ""
    baseline_dataset: BaselineDataset | None = None
    benchmark_id: str = Field(min_length=1)
    prompt_version: str = ""
    evaluation_version: str = Field(min_length=1)
    timestamp: str = ""
    result: BenchmarkScores
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class ExperimentRun(BaseModel):
    """A trained/adapted evaluation run; adaptation is metadata (§13–§14)."""

    model_config = {"frozen": True}

    run_id: str = Field(min_length=1)
    training_dataset_release_id: str | None = None
    training_config: dict[str, Any] = Field(default_factory=dict)
    model_base: str = Field(min_length=1)
    model_revision: str = ""
    adaptation_method: AdaptationMethod = "NONE"
    benchmark_id: str = Field(min_length=1)
    timestamp: str = ""
    result: BenchmarkScores
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class ArmSpec(BaseModel):
    """One experiment arm (baseline, control, or treatment)."""

    model_config = {"frozen": True}

    model: str = Field(min_length=1)
    model_revision: str = ""
    dataset_release_id: str | None = None
    baseline_dataset_id: str | None = None
    adaptation_method: AdaptationMethod = "NONE"
    training_config: dict[str, Any] = Field(default_factory=dict)


class ExperimentConfig(BaseModel):
    """Content-addressed experiment contract (§23–§24)."""

    model_config = {"frozen": True}

    experiment_id: str = Field(min_length=1)
    experiment_version: str = Field(min_length=1)
    benchmark_id: str = Field(min_length=1)
    baseline: ArmSpec
    control: ArmSpec | None = None
    treatment: ArmSpec
    evaluation_config: dict[str, Any] = Field(default_factory=dict)
    seeds: list[int] = Field(default_factory=list)
    scoring_method: str = Field(min_length=1)
    prompt_version: str = ""
    code_revision: str | None = None
    environment: str | None = None
    config_version: str = Field(default="1.0", min_length=1)
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class ImprovementMetrics(BaseModel):
    """Deltas with explicit denominators (§18). Never a single score."""

    model_config = {"frozen": True}

    metric: str = Field(min_length=1)
    baseline: float
    treatment: float
    denominator_n: int = Field(ge=0)
    absolute_pp: float
    relative_pct: float | None = None
    error_reduction: float | None = None


class FamilyDelta(BaseModel):
    model_config = {"frozen": True}

    family: str = Field(min_length=1)
    baseline: float | None = None
    treatment: float | None = None
    delta_pp: float | None = None
    n: int = Field(ge=0)


class EdgeDelta(BaseModel):
    model_config = {"frozen": True}

    edge_case: str = Field(min_length=1)
    baseline: float | None = None
    treatment: float | None = None
    delta_pp: float | None = None
    n: int = Field(ge=0)


class StatisticalEvidence(BaseModel):
    """Paired-binary statistics with honest power reporting (§19)."""

    model_config = {"frozen": True}

    method: StatMethod = "NONE"
    n: int = Field(ge=0)
    baseline: float | None = None
    treatment: float | None = None
    delta_pp: float | None = None
    ci_low_pp: float | None = None
    ci_high_pp: float | None = None
    baseline_ci: tuple[float, float] | None = None
    treatment_ci: tuple[float, float] | None = None
    p_value: float | None = None
    discordant_pairs: int = Field(ge=0, default=0)
    warnings: list[str] = Field(default_factory=list)
    sufficient: bool = False


class RepeatedRunSummary(BaseModel):
    """Run-to-run variance over repeated evaluations (§20)."""

    model_config = {"frozen": True}

    n: int = Field(ge=0)
    mean: float | None = None
    std: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    values: list[float] = Field(default_factory=list)


class ArtifactRef(BaseModel):
    """Reference to a large artifact; contents never embedded (§50)."""

    model_config = {"frozen": True}

    artifact_id: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    size: int = Field(ge=0)
    relative_locator: str = Field(min_length=1)


class ExperimentResult(BaseModel):
    """Full experiment outcome incl. failures and reproducibility refs (§25)."""

    model_config = {"frozen": True}

    experiment_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    status: RunStatus = "COMPLETED"
    baseline_metrics: BenchmarkScores
    treatment_metrics: BenchmarkScores
    control_metrics: BenchmarkScores | None = None
    deltas: list[ImprovementMetrics] = Field(default_factory=list)
    statistical_evidence: StatisticalEvidence | None = None
    family_table: list[FamilyDelta] = Field(default_factory=list)
    edge_table: list[EdgeDelta] = Field(default_factory=list)
    failure_modes: list[FailureMode] = Field(default_factory=list)
    failure_notes: list[str] = Field(default_factory=list)
    reproducibility: dict[str, Any] = Field(default_factory=dict)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    created_at: str = ""
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class ExperimentComparison(BaseModel):
    """Presentation-ready comparison; per-metric/family/edge rows (§26)."""

    model_config = {"frozen": True}

    experiment_id: str = Field(min_length=1)
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    families: list[FamilyDelta] = Field(default_factory=list)
    edge_cases: list[EdgeDelta] = Field(default_factory=list)
    sample_size: int = Field(ge=0)
    verdict: HypothesisVerdict = "INSUFFICIENT_EVIDENCE"
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class CostModel(BaseModel):
    """Production cost inputs; unknown stays None, never silent zero (§27–§28)."""

    model_config = {"frozen": True}

    currency: str = Field(default="USD", min_length=1)
    variable_costs: dict[str, float | None] = Field(default_factory=dict)
    fixed_costs: dict[str, float | None] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    measured: bool = False
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class UnitEconomics(BaseModel):
    model_config = {"frozen": True}

    total_cost: float | None = None
    golden_records: int = Field(ge=0)
    cost_per_golden: float | None = None
    cost_per_1000_golden: float | None = None
    cost_per_million_golden: float | None = None
    unknown_inputs: list[str] = Field(default_factory=list)
    basis: ValueBasis = "ASSUMED"
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class CostScenario(BaseModel):
    """Scale scenario explicitly labeled SCENARIO, never FORECAST (§29)."""

    model_config = {"frozen": True}

    label: Literal["SCENARIO"] = "SCENARIO"
    scale_records: int = Field(gt=0)
    total_cost: float | None = None
    cost_per_golden: float | None = None
    assumptions: list[str] = Field(default_factory=list)
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class CustomerSegment(BaseModel):
    """A hypothesized segment; hypotheses, not proven demand (§30)."""

    model_config = {"frozen": True}

    segment: str = Field(min_length=1)
    problem: str = Field(min_length=1)
    use_case: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    validation_status: Maturity = "HYPOTHESIS"
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class UseCase(BaseModel):
    model_config = {"frozen": True}

    use_case: str = Field(min_length=1)
    problem: str = Field(min_length=1)
    current_alternative: str = ""
    pain_point: str = ""
    product_fit: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    status: Maturity = "HYPOTHESIS"
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class CustomerValidation(BaseModel):
    """One customer interaction record; no personal names or contacts (§32).

    Contact identity is intentionally not a field: role-level records
    only. ``evidence_reference`` is required for purchase-level signals.
    """

    model_config = {"frozen": True}

    validation_id: str = Field(min_length=1)
    organization: str = Field(min_length=1)
    segment: str = Field(min_length=1)
    contact_role: str = ""
    use_case: str = ""
    problem_statement: str = ""
    current_solution: str = ""
    dataset_release_tested: str | None = None
    pilot_status: PilotStatus | None = None
    feedback: FeedbackClass = "NO_DECISION"
    feedback_text: str | None = None
    requested_features: list[str] = Field(default_factory=list)
    willingness_signal: WillingnessSignal | None = None
    purchase_signal: bool = False
    evidence_type: EvidenceStatus = "UNKNOWN"
    evidence_reference: str = ""
    timestamp: str = ""
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class SuccessCriterion(BaseModel):
    """One configurable pilot acceptance rule (§35). No universal thresholds."""

    model_config = {"frozen": True}

    criterion_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    threshold: float
    comparison: Literal["gte", "lte"] = "gte"
    outcome: CriterionOutcome = "UNEVALUATED"


class Pilot(BaseModel):
    """Lightweight pilot tracker; research structure, not a CRM (§34)."""

    model_config = {"frozen": True}

    pilot_id: str = Field(min_length=1)
    product_release_id: str = Field(min_length=1)
    customer_segment: str = Field(min_length=1)
    use_case: str = ""
    success_criteria: list[SuccessCriterion] = Field(default_factory=list)
    start_date: str | None = None
    end_date: str | None = None
    status: PilotStatus = "PLANNED"
    results: dict[str, Any] = Field(default_factory=dict)
    feedback_ids: list[str] = Field(default_factory=list)
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class CommercialFunnel(BaseModel):
    """Observed stage counts; a measurement system, no fake entries (§44)."""

    model_config = {"frozen": True}

    counts: dict[str, int] = Field(default_factory=dict)
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class CommercialExperiment(BaseModel):
    """Pricing/format/offer tests. No payment collection (§54)."""

    model_config = {"frozen": True}

    experiment_id: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    variant: str = Field(min_length=1)
    population: str = ""
    measurement: str = ""
    result: str | None = None
    status: CommercialStatus = "PLANNED"
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class ProductOffer(BaseModel):
    """Offer descriptor; engineering-complete is not production-ready (§41)."""

    model_config = {"frozen": True}

    offer_id: str = Field(min_length=1)
    product_release_id: str = Field(min_length=1)
    target_segment: str = Field(min_length=1)
    use_case: str = ""
    delivery_format: str = ""
    support_level: str = ""
    commercial_status: OfferStatus = "EXPERIMENTAL"
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class PricingScenario(BaseModel):
    """Price hypothesis; ASSUMED until customer behavior validates (§42)."""

    model_config = {"frozen": True}

    scenario_id: str = Field(min_length=1)
    product_release_id: str | None = None
    assumed_price: float = Field(ge=0.0)
    pricing_unit: PricingUnit = "DATASET"
    cost_basis: float | None = None
    target_margin: float | None = None
    assumptions: list[str] = Field(default_factory=list)
    basis: ValueBasis = "ASSUMED"
    evidence_ids: list[str] = Field(default_factory=list)
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class ExternalDatasetRef(BaseModel):
    """External/competitor dataset recorded as reference, never copied (§52)."""

    model_config = {"frozen": True}

    source_name: str = Field(min_length=1)
    source_url: str | None = None
    license_identifier: str | None = None
    version: str | None = None
    observed_attributes: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class HypothesisCriteria(BaseModel):
    """Configurable acceptance criteria for the core thesis (§56)."""

    model_config = {"frozen": True}

    primary_metric: str = "execution_accuracy"
    improvement_threshold_pp: float = 0.0
    minimum_benchmark_size: int = Field(ge=0, default=0)
    minimum_repeated_runs: int = Field(ge=0, default=0)
    minimum_family_coverage: int = Field(ge=0, default=0)


class RoadmapEvidence(BaseModel):
    """Evidence for human strategy decisions; never auto-decides (§59)."""

    model_config = {"frozen": True}

    validated_needs: list[str] = Field(default_factory=list)
    unvalidated_assumptions: list[str] = Field(default_factory=list)
    technical_gaps: list[str] = Field(default_factory=list)
    product_gaps: list[str] = Field(default_factory=list)
    customer_requests: list[str] = Field(default_factory=list)
    experiment_gaps: list[str] = Field(default_factory=list)
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)


class BusinessValidationReport(BaseModel):
    """Auditable business answer; sections never collapse to one score (§47)."""

    model_config = {"frozen": True}

    report_id: str = Field(min_length=1)
    created_at: str = ""
    product: dict[str, Any] = Field(default_factory=dict)
    model_value: dict[str, Any] = Field(default_factory=dict)
    customer: dict[str, Any] = Field(default_factory=dict)
    economics: dict[str, Any] = Field(default_factory=dict)
    gtm: dict[str, Any] = Field(default_factory=dict)
    maturity: dict[str, Any] = Field(default_factory=dict)
    known: list[str] = Field(default_factory=list)
    measured: list[str] = Field(default_factory=list)
    customer_said: list[str] = Field(default_factory=list)
    assumed: list[str] = Field(default_factory=list)
    unknown: list[str] = Field(default_factory=list)
    hypothesis_verdict: HypothesisVerdict = "INSUFFICIENT_EVIDENCE"
    hypothesis_detail: str = ""
    schema_version: str = Field(default=BUSINESS_SCHEMA_VERSION, min_length=1)
