"""Test-only fake container runner (Phase 3).

Scripts single-shot container outcomes without Docker: exit code, stdout
(result JSON), stderr, and failures are programmable, and every call is
recorded so tests can assert isolation flags, payload delivery, cleanup,
and timeout behavior. NEVER used in production paths.
"""

from __future__ import annotations

import json
from typing import Any

from .docker import ContainerRunner
from .errors import DockerError, RunnerTimeoutError
from .models import RunResult


class FakeDockerRunner(ContainerRunner):
    """Scripted runner over the stdin/stdout container contract."""

    def __init__(
        self,
        exit_code: int = 0,
        stdout: bytes | str | dict[str, Any] | None = None,
        stderr: bytes | str = b"",
        output_files: dict[str, Any] | None = None,
        image_digest: str | None = "sha256:fake",
        fail_on: str | None = None,
        hang: bool = False,
    ) -> None:
        if stdout is None and output_files and "result.json" in output_files:
            stdout = output_files["result.json"]
        if isinstance(stdout, dict):
            stdout = json.dumps(stdout)
        if isinstance(stdout, str):
            stdout = stdout.encode()
        if isinstance(stderr, str):
            stderr = stderr.encode()
        self._exit_code = exit_code
        self._stdout = stdout if stdout is not None else b"OK\n"
        self._stderr = stderr
        self._image_digest = image_digest
        self._fail_on = fail_on
        self._hang = hang
        self.calls: list[str] = []
        self.killed: list[str] = []
        self.removed: list[str] = []
        self.payloads: list[bytes] = []

    def _maybe_fail(self, step: str) -> None:
        self.calls.append(step)
        if self._fail_on == step:
            raise DockerError(f"fake {step} failure")

    def run_container(
        self, name: str, execution_id: str, payload: bytes, timeout_s: float
    ) -> RunResult:
        self._maybe_fail("run")
        self.payloads.append(payload)
        if self._hang:
            self.killed.append(name)
            raise RunnerTimeoutError("fake run timed out")
        return RunResult(exit_code=self._exit_code, stdout=self._stdout, stderr=self._stderr)

    def remove(self, name: str) -> None:
        self.removed.append(name)
        self.calls.append("remove")

    def image_digest(self) -> str | None:
        return self._image_digest
