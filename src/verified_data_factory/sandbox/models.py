"""Execution data models (Phase 3).

These models describe *what happened during execution* — never whether
the candidate is correct. There is intentionally no ``is_correct``,
``CORRECT``, ``INCORRECT``, or ``VERIFIED`` anywhere in this module.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SANDBOX_CONFIG_VERSION = "1.0"


class RunResult(BaseModel):
    """Raw outcome of one disposable container run (bytes, uncapped)."""

    model_config = {"frozen": True, "arbitrary_types_allowed": True}

    exit_code: int
    stdout: bytes
    stderr: bytes


ExecutionStatus = Literal[
    "NOT_STARTED",
    "STARTING",
    "RUNNING",
    "SUCCEEDED",
    "TIMEOUT",
    "RESOURCE_LIMIT",
    "RESULT_LIMIT",
    "SANDBOX_ERROR",
    "EXECUTION_ERROR",
    "POLICY_REJECTED",
]

#: Statuses an ExecutionResult may actually carry. Lifecycle states exist
#: for completeness but are never emitted on results (asserted by test).
TERMINAL_STATUSES = frozenset(
    {
        "SUCCEEDED",
        "TIMEOUT",
        "RESOURCE_LIMIT",
        "RESULT_LIMIT",
        "SANDBOX_ERROR",
        "EXECUTION_ERROR",
        "POLICY_REJECTED",
    }
)

FailureCode = Literal[
    "INVALID_INPUT",
    "POLICY_REJECTED",
    "SANDBOX_START_FAILED",
    "TIMEOUT",
    "RESOURCE_LIMIT",
    "EXECUTION_ERROR",
    "RESULT_LIMIT",
    "SANDBOX_CLEANUP_ERROR",
    "INTERNAL_ERROR",
]


class FailureInfo(BaseModel):
    model_config = {"frozen": True}

    code: FailureCode
    message: str = Field(min_length=1)
    detail: dict[str, Any] = Field(default_factory=dict)


class ResultColumn(BaseModel):
    model_config = {"frozen": True}

    name: str
    type: str


class ResultData(BaseModel):
    model_config = {"frozen": True}

    columns: list[ResultColumn] = Field(default_factory=list)
    rows: list[list[Any]] = Field(default_factory=list)
    rows_returned: int = Field(ge=0)
    truncated: bool = False


class ResourceUsage(BaseModel):
    model_config = {"frozen": True}

    duration_ms: int = Field(ge=0)
    max_memory_mb: float | None = None
    output_bytes: int = Field(ge=0, default=0)


class ResourceLimits(BaseModel):
    """Echo of the applied limits (provenance, not enforcement)."""

    model_config = {"frozen": True}

    timeout_seconds: float
    memory_mb: int
    cpus: float
    pids_limit: int
    max_result_rows: int
    max_result_bytes: int
    max_stdout_bytes: int
    max_stderr_bytes: int


class ExecutionResult(BaseModel):
    model_config = {"frozen": True, "populate_by_name": True}

    execution_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    status: ExecutionStatus
    failure: FailureInfo | None = None
    result_data: ResultData | None = None
    stdout: str = ""
    stderr: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    exit_code: int | None = None
    duration_ms: int = Field(ge=0)
    resource_limits: ResourceLimits
    resource_usage: ResourceUsage
    sandbox_image: str = Field(min_length=1)
    sandbox_image_digest: str | None = None
    sandbox_config_version: str = Field(min_length=1)
    duckdb_version: str | None = None
    started_at: str = Field(min_length=1)
    finished_at: str = Field(min_length=1)
