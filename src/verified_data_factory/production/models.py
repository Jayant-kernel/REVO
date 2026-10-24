from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

FAMILIES = (
    "simple_joins", "multi_joins", "aggregation", "cte", "subqueries",
    "window_functions", "temporal", "deduplication", "retention", "funnel",
)


class ProductionModel(BaseModel):
    model_config = {"frozen": True}
    model_id: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    provider: Literal["devstral", "qwen"]
    governance_status: Literal[
        "REVIEW_REQUIRED_NON_COMMERCIAL", "COMMERCIALLY_CLEARED"
    ]
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
    batches_per_authorization: int = Field(default=1, ge=1, le=1)
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
    review_pool_mode: bool = False
    min_distinct_templates_per_family: int = Field(default=1, ge=1)
    pause_conditions: dict[str, float | int] = Field(default_factory=dict)
    diversity_warnings: dict[str, float] = Field(default_factory=dict)
    private_benchmark_target: int = Field(default=150, ge=100, le=200)
    business_hypothesis: str = "INSUFFICIENT_EVIDENCE"
    schedule_mode: Literal["legacy", "distinct_contract"] = "legacy"
    selected_contract_ids: dict[str, list[str]] = Field(default_factory=dict)
    distinct_contract_selection: Literal["contract_id_ascending"] = "contract_id_ascending"

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
    def safe_budget_and_path(self) -> ProductionConfig:
        if self.initial_task_batch * self.candidates_per_task > self.budget.max_total_candidates:
            raise ValueError("initial candidate volume exceeds max_total_candidates")
        if self.initial_task_batch > self.budget.max_total_tasks:
            raise ValueError("initial task batch exceeds max_total_tasks")
        if self.output_dir.rstrip("/\\").endswith("production-001"):
            raise ValueError("output_dir must not reuse historical production-001")
        if self.schedule_mode == "distinct_contract" and set(self.selected_contract_ids) != set(FAMILIES):
            raise ValueError("distinct_contract mode must select contract IDs for every family")
        if any(not contract_id for ids in self.selected_contract_ids.values() for contract_id in ids):
            raise ValueError("selected contract IDs must be nonempty")
        return self
