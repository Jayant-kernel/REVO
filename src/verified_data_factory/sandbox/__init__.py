"""Stable public API for Secure Execution (Phase 3 consumers).

Phase 4 calls :func:`execute_candidate` and receives an ``ExecutionResult``
describing only what happened — no verdicts, no oracle comparisons.
"""

from .api import execute_candidate
from .config import SandboxConfig, config_from_dict, load_config
from .docker import ContainerRunner, DockerRunner, docker_available, fresh_container_name
from .errors import DockerError, RunnerTimeoutError, SandboxConfigError, SandboxError
from .executor import SandboxExecutor, build_execution_id
from .fake import FakeDockerRunner
from .fixture import build_execution_package, build_execution_payload
from .models import (
    SANDBOX_CONFIG_VERSION,
    TERMINAL_STATUSES,
    ExecutionResult,
    ExecutionStatus,
    FailureCode,
    FailureInfo,
    ResourceLimits,
    ResourceUsage,
    ResultColumn,
    ResultData,
    RunResult,
)
from .policy import PolicyDecision, check_policy, classify_statement, split_statements

__all__ = [
    "SANDBOX_CONFIG_VERSION",
    "TERMINAL_STATUSES",
    "ContainerRunner",
    "DockerError",
    "DockerRunner",
    "ExecutionResult",
    "ExecutionStatus",
    "FailureCode",
    "FailureInfo",
    "FakeDockerRunner",
    "PolicyDecision",
    "ResourceLimits",
    "ResourceUsage",
    "ResultColumn",
    "ResultData",
    "RunResult",
    "RunnerTimeoutError",
    "SandboxConfig",
    "SandboxConfigError",
    "SandboxError",
    "SandboxExecutor",
    "build_execution_id",
    "build_execution_package",
    "build_execution_payload",
    "check_policy",
    "classify_statement",
    "config_from_dict",
    "docker_available",
    "execute_candidate",
    "fresh_container_name",
    "load_config",
    "split_statements",
]
