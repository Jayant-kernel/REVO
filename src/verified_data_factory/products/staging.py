"""Strict releases publish only after validation under a fixed factory authority."""
from __future__ import annotations

import json
import os
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from verified_data_factory.local_lock import exclusive_lock
from verified_data_factory.local_paths import io_path

from .errors import ProductConfigError


class PublishedRelease(Protocol):
    release_dir: Path


def isolation_authority(root: Path, registry: Path) -> dict[str, Any]:
    """Call under the fixed authority lock, before reserving any role."""
    path = root / "manifests/engineering-isolation-authority.json"
    if path.exists():
        authority = json.loads(path.read_text())
        if (authority.get("version") != 1 or not authority.get("registry_id")
                or Path(authority["registry_path"]).resolve() != registry.resolve()):
            raise ProductConfigError("persistent isolation authority differs; registry path cannot change")
        return dict(authority)
    authority = {"version": 1, "registry_id": uuid4().hex, "registry_path": str(registry.resolve())}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(authority, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    return authority


def staged_release[R: PublishedRelease](build: Callable[..., R]) -> Callable[..., R]:
    @wraps(build)
    def wrapped(*args: Any, **kwargs: Any) -> R:
        values: dict[str, Any] = dict(kwargs)
        config = values.get("config")
        if config is None or config.acceptance_profile != "ENGINEERING_STRICT":
            return build(*args, **kwargs)
        if not config.engineering_evidence_root or not config.engineering_role_registry:
            raise ProductConfigError("engineering evidence root and persistent role registry required")
        root = Path(config.engineering_evidence_root).resolve()
        final = Path(values["out_dir"]).resolve()
        with exclusive_lock(root / "manifests/engineering-isolation-authority.lock"):
            if not (root / "manifests/engineering-isolation-authority.json").exists():
                from verified_data_factory.verification.readiness import qualify

                from .release import _snapshot_member

                members = set(values["snapshot"].golden_record_ids)
                goldens = [g for g in values["golden_records"] if _snapshot_member(g, members)]
                if any(not any(_snapshot_member(g, {member}) for g in goldens) for member in members):
                    raise ProductConfigError("engineering snapshot members were not all supplied")
                if not goldens:
                    raise ProductConfigError("no supplied golden records are members of the dataset snapshot")
                for golden in goldens:
                    evidence = values["quality_by_id"].get(golden.candidate_id, {}).get("engineering_record")
                    if not isinstance(evidence, dict) or not qualify(root, evidence)["eligible"]:
                        raise ProductConfigError("fresh engineering qualification record missing or stale")
            isolation_authority(root, Path(config.engineering_role_registry))
            if final.exists():
                raise ProductConfigError("engineering release destination must be new")
            staging = io_path(final.parent / f".{final.name}.staging-{uuid4().hex}")
            values["out_dir"] = staging
            # Failed private staging is retained for diagnosis. No final path exists.
            result = build(**values)
            if final.exists():
                raise ProductConfigError("late release destination conflict")
            staging.replace(final)
            result.release_dir = final
            return result
    return wrapped
