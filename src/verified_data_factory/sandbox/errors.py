"""Sandbox exceptions (Phase 3).

Policy rejections and execution outcomes are returned as ``ExecutionResult``
data, never raised. Exceptions here signal harness/config programming
errors only.
"""

from __future__ import annotations


class SandboxError(Exception):
    """Base error for sandbox harness failures."""


class SandboxConfigError(SandboxError):
    """Invalid sandbox configuration."""


class DockerError(SandboxError):
    """Docker CLI invocation or container lifecycle failure."""


class RunnerTimeoutError(SandboxError):
    """Container did not finish within the execution timeout."""
