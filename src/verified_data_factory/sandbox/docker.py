"""Docker invocation layer (Phase 3).

Strict separation: this module knows Docker flags and container lifecycle,
nothing about tasks, candidates, or SQL. Candidate SQL is NEVER placed in
argv or shell commands — it travels inside a single stdin JSON payload.
No bind mounts exist anywhere in this module (provable by inspection:
no ``-v``/``--volume``/``--mount`` flags) and no ``docker cp`` is used
(the daemon rejects copies into read-only-rootfs containers, so delivery
is stdin-only by construction).
"""

from __future__ import annotations

import abc
import subprocess
import uuid

from .config import SandboxConfig
from .errors import DockerError, RunnerTimeoutError
from .models import RunResult


class ContainerRunner(abc.ABC):
    """Container lifecycle abstraction (lets tests fake Docker)."""

    @abc.abstractmethod
    def run_container(
        self, name: str, execution_id: str, payload: bytes, timeout_s: float
    ) -> RunResult:
        """Run one disposable container to completion.

        Delivers ``payload`` on stdin, captures stdout/stderr, enforces
        ``timeout_s`` (killing on expiry). Raises RunnerTimeoutError on
        timeout, DockerError on startup failure.
        """

    @abc.abstractmethod
    def remove(self, name: str) -> None:
        """Remove a container by name (best effort, force)."""

    @abc.abstractmethod
    def image_digest(self) -> str | None:
        """Best-effort image digest for provenance (None if unavailable)."""


class DockerRunner(ContainerRunner):
    """Real Docker CLI runner with the Phase 3 isolation flags."""

    def __init__(
        self,
        config: SandboxConfig,
        docker_bin: str = "docker",
        control_timeout_s: float = 60.0,
    ) -> None:
        self._config = config
        self._docker = docker_bin
        self._control_timeout_s = control_timeout_s

    def _isolation_args(self, name: str, execution_id: str) -> list[str]:
        cfg = self._config
        mem = f"{cfg.memory_mb}m"
        if not cfg.read_only_root or not cfg.non_root or not cfg.cap_drop_all:
            raise DockerError("refusing to run a container with weakened isolation flags")
        if cfg.no_new_privileges is False:
            raise DockerError("refusing to run a container with weakened isolation flags")
        return [
            "run",
            "--name",
            name,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            mem,
            "--memory-swap",
            mem,
            "--cpus",
            str(cfg.cpus),
            "--pids-limit",
            str(cfg.pids_limit),
            "--user",
            "10000:10000",
            "--workdir",
            "/work",
            "--tmpfs",
            "/tmp:size=64m,mode=1777",
            "--tmpfs",
            "/work/tmp:size=64m,mode=1777",
            "--stop-timeout",
            "5",
            "--env",
            f"VDF_EXECUTION_ID={execution_id}",
            "-i",
            cfg.image,
            "python",
            "/harness/run.py",
            "--stdin",
        ]

    def run_container(
        self, name: str, execution_id: str, payload: bytes, timeout_s: float
    ) -> RunResult:
        args = self._isolation_args(name, execution_id)
        try:
            proc = subprocess.Popen(
                [self._docker, *args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise DockerError(f"docker invocation failed: {exc}") from exc
        try:
            stdout, stderr = proc.communicate(payload, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            self.kill(name)
            try:
                stdout, stderr = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
            raise RunnerTimeoutError(f"container {name} exceeded {timeout_s}s; killed") from None
        if proc.returncode != 0 and stderr.startswith(b"docker: "):
            # CLI/daemon error (bad flags, missing image, name clash) —
            # not a harness result. Tracebacks start with "Traceback", so
            # this prefix check cannot misclassify a harness crash.
            raise DockerError(f"docker run failed: {stderr[:500]!r}")
        return RunResult(
            exit_code=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def kill(self, name: str) -> None:
        try:
            subprocess.run(
                [self._docker, "kill", name],
                capture_output=True,
                timeout=self._control_timeout_s,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass

    def remove(self, name: str) -> None:
        try:
            subprocess.run(
                [self._docker, "rm", "-f", name],
                capture_output=True,
                timeout=self._control_timeout_s,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass

    def image_digest(self) -> str | None:
        try:
            completed = subprocess.run(
                [self._docker, "image", "inspect", "--format", "{{.Id}}", self._config.image],
                capture_output=True,
                text=True,
                timeout=self._control_timeout_s,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if completed.returncode != 0:
            return None
        digest = completed.stdout.strip()
        return digest or None


def fresh_container_name() -> str:
    """Unique container name (no reliance on prior cleanup)."""
    return f"vdf-{uuid.uuid4().hex[:16]}"


def docker_available(docker_bin: str = "docker", timeout_s: float = 15.0) -> bool:
    """Whether a Docker daemon answers (integration-test gate)."""
    try:
        completed = subprocess.run(
            [docker_bin, "info"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0
