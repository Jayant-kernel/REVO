"""Pydantic models for Candidate Generation (Phase 2).

Deliberately absent: ``is_correct``, ``verification_status``,
``test_status`` or any correctness notion — those belong to Phase 4.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

GENERATION_SCHEMA_VERSION = "1.0"
PROMPT_VERSION = "sql-v2"
SQL_DIALECT = "DuckDB"

GenerationStatus = Literal["success", "provider_failed"]
ParseStatus = Literal["success", "failed"]


class GenerationConfig(BaseModel):
    """Sampling configuration. Only parameters the provider supports."""

    model_config = {"frozen": True}

    temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)
    max_tokens: int = Field(default=2048, ge=1, le=32768)
    seed: int | None = Field(default=None, ge=0)


class TokenUsage(BaseModel):
    model_config = {"frozen": True}

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class GenerationResponse(BaseModel):
    """Normalized provider output. No provider-specific types leak past here."""

    model_config = {"frozen": True}

    raw_text: str
    model: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    finish_reason: str = Field(default="unknown")
    token_usage: TokenUsage | None = None
    generation_time_ms: int = Field(ge=0)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateSolution(BaseModel):
    """One candidate SQL solution for one task. Correctness-free by design."""

    model_config = {"frozen": True, "populate_by_name": True}

    candidate_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    generation_schema_version: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    endpoint_id: str = Field(min_length=1)
    candidate_index: int = Field(ge=0)
    raw_response: str
    candidate_sql: str | None = None
    generation_config: GenerationConfig
    generation_timestamp: str = Field(min_length=1)
    generation_duration_ms: int = Field(ge=0)
    finish_reason: str = Field(default="unknown")
    token_usage: TokenUsage | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)
    generation_status: GenerationStatus = "success"
    parse_status: ParseStatus = "success"
    failure_reason: str | None = None


class GenerationResult(BaseModel):
    """Outcome of one generation attempt; failures are data, not crashes."""

    model_config = {"frozen": True}

    generation_status: GenerationStatus
    parse_status: ParseStatus
    candidate_solution: CandidateSolution | None = None
    failure_reason: str | None = None
