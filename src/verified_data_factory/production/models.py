from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


FAMILIES = (
    "simple_joins", "multi_joins", "aggregation", "cte", "subqueries",
    "window_functions", "temporal", "deduplication", "retention", "funnel",
)


class ProductionModel(BaseModel):
    model_config = {"frozen": True}
    model_id: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    endpoint: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    parser_version: str = Field(min_length=1)
    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(ge=0, le=1)
    max_tokens: int = Field(ge=1)


class Budget(BaseModel):
    model_config = {"frozen": True}
    max_total_tasks: int = Field(ge=1)
    max_total_candidates: int = Field(ge=1)
    max_wall_time_minutes: int = Field(ge=1)


class AuditPolicy(BaseModel):
    model_config = {"frozen": True}
    sample_size: int = Field(ge=1)
    risk_based_selection: bool = True
    seed: int = 42


class ProductionConfig(BaseModel):
    model_config = {"frozen": True}
    config_version: str = Field(min_length=1)
    run_name: str = Field(min_length=1)
    target_golden_records: int = Field(ge=1)
    initial_task_batch: int = Field(ge=1)
    candidates_per_task: int = Field(ge=1)
    max_batches: int = Field(ge=1)
    output_dir: str = Field(min_length=1)
    seed: int = Field(ge=0)
    model: ProductionModel
    budget: Budget
    family_distribution: dict[str, int]
    quality_config: str = Field(min_length=1)
    sandbox_config: str = Field(min_length=1)
    provenance_config: str = Field(min_length=1)
    product_config: str = Field(min_length=1)
    audit: AuditPolicy
    pause_conditions: dict[str, float | int] = Field(default_factory=dict)
    diversity_warnings: dict[str, float] = Field(default_factory=dict)
    private_benchmark_target: int = Field(default=150, ge=100, le=200)
    business_hypothesis: str = "INSUFFICIENT_EVIDENCE"

    @field_validator("model")
    @classmethod
    def exact_revision_required(cls, value: ProductionModel) -> ProductionModel:
        if value.model_revision in {"", "unspecified", "latest"}:
            raise ValueError("model_revision must pin an exact non-mutable revision")
        if value.prompt_version != "sql-v2":
            raise ValueError("production prompt_version must be sql-v2")
        return value

    @field_validator("family_distribution")
    @classmethod
    def all_families_balanced(cls, value: dict[str, int]) -> dict[str, int]:
        if set(value) != set(FAMILIES) or any(count < 1 for count in value.values()):
            raise ValueError("family_distribution must cover every family with positive counts")
        return value

    @model_validator(mode="after")
    def safe_budget_and_path(self) -> "ProductionConfig":
        if self.initial_task_batch * self.candidates_per_task > self.budget.max_total_candidates:
            raise ValueError("initial candidate volume exceeds max_total_candidates")
        if self.initial_task_batch > self.budget.max_total_tasks:
            raise ValueError("initial task batch exceeds max_total_tasks")
        if self.output_dir.rstrip("/\\").endswith("production-001"):
            raise ValueError("output_dir must not reuse historical production-001")
        return self
