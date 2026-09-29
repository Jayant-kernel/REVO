"""Environment snapshots (Phase 6, §14).

Captures versions, never secrets: only the *names* of a small documented
set of environment variables are recorded (values never leave the host).
Docker/DuckDB metadata is best-effort with honest UNAVAILABLE states.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

from .hashing import content_id, hash_file
from .models import PROVENANCE_SCHEMA_VERSION, EnvironmentSnapshot

# Variable names whose *presence* is reproducibility-relevant. Values are
# never recorded (they may carry paths, keys, or other sensitive data).
SAFE_ENV_NAMES = ("PYTHONHASHSEED", "TZ", "LANG", "LC_ALL", "DOCKER_HOST", "CUDA_VISIBLE_DEVICES")


def _docker_version(args: list[str]) -> str | None:
    if shutil.which("docker") is None:
        return None
    try:
        completed = subprocess.run(
            ["docker", *args], capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _duckdb_version() -> str | None:
    try:
        import duckdb

        return duckdb.__version__
    except Exception:  # noqa: BLE001 — optional dependency probe
        return None


def _dependency_lock_hash(repo_root: Path) -> str:
    lockfile = repo_root / "pyproject.toml"
    if lockfile.is_file():
        try:
            content_hash, _ = hash_file(lockfile)
            return content_hash
        except OSError:
            return "UNKNOWN"
    return "UNKNOWN"


def capture_environment_snapshot(
    repo_root: str | Path,
    container_image: str | None = None,
    container_image_digest: str | None = None,
    container_python_version: str | None = None,
    container_duckdb_version: str | None = None,
) -> EnvironmentSnapshot:
    """Snapshot safe runtime metadata (versions, never secret values)."""
    repo = Path(repo_root)
    digest_status: Literal["PINNED", "RECORDED", "UNAVAILABLE"]
    if container_image_digest and container_image:
        digest_status = "PINNED"
    elif container_image_digest:
        digest_status = "RECORDED"
    else:
        digest_status = "UNAVAILABLE"
    payload = {
        "python_version": sys.version.split()[0],
        "platform": platform.system(),
        "architecture": platform.machine(),
        "operating_system": platform.platform(),
        "docker_client_version": _docker_version(["version", "--format", "{{.Client.Version}}"]),
        "docker_server_version": _docker_version(["version", "--format", "{{.Server.Version}}"]),
        "duckdb_version": _duckdb_version(),
        "dependency_lock_hash": _dependency_lock_hash(repo),
        "container_image": container_image,
        "container_image_digest": container_image_digest,
        "image_digest_status": digest_status,
        "container_python_version": container_python_version,
        "container_duckdb_version": container_duckdb_version,
        "observed_env_names": sorted(n for n in SAFE_ENV_NAMES if n in os.environ),
    }
    return EnvironmentSnapshot(
        environment_snapshot_id=content_id(
            "ENVIRONMENT_SNAPSHOT", PROVENANCE_SCHEMA_VERSION, payload
        ),
        python_version=payload["python_version"],
        platform=payload["platform"],
        architecture=payload["architecture"],
        operating_system=payload["operating_system"],
        docker_client_version=payload["docker_client_version"],
        docker_server_version=payload["docker_server_version"],
        duckdb_version=payload["duckdb_version"],
        dependency_lock_hash=payload["dependency_lock_hash"],
        container_image=payload["container_image"],
        container_image_digest=payload["container_image_digest"],
        image_digest_status=digest_status,
        container_python_version=payload["container_python_version"],
        container_duckdb_version=payload["container_duckdb_version"],
        schema_version=PROVENANCE_SCHEMA_VERSION,
    )
