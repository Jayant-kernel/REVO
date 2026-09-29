"""Source snapshots (Phase 6, §38).

Scope (documented reproducibility boundary): the ``source_scope``
directories from :class:`ProvenanceConfig` (default: the package source,
``pyproject.toml``, ``configs/``). Generated data, caches, and anything
outside the scope are never hashed.

Fingerprint strategy: ``git ls-tree -r HEAD`` when the tree is clean
(exact blob manifest); when dirty or git is absent, fall back to hashing
the scoped files directly while recording the dirty/unknown state loudly.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .hashing import content_id, hash_file
from .models import PROVENANCE_SCHEMA_VERSION, SourceSnapshot


def _git(repo: Path, *args: str) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return completed.returncode == 0, completed.stdout.strip()


def _repository_name(repo: Path) -> str:
    ok, url = _git(repo, "config", "--get", "remote.origin.url")
    if ok and url:
        return url
    return repo.resolve().name


def capture_source_snapshot(repo_root: str | Path, scope: list[str]) -> SourceSnapshot:
    """Snapshot repository state; never invent a clean bill of health."""
    repo = Path(repo_root)
    name = _repository_name(repo)
    ok_commit, commit = _git(repo, "rev-parse", "HEAD")
    ok_branch, branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    ok_status, status = _git(repo, "status", "--porcelain")
    clean = ok_status and status == "" and ok_commit

    fingerprint = "UNKNOWN"
    if ok_commit:
        ok_tree, tree = _git(repo, "ls-tree", "-r", "HEAD")
        if ok_tree and tree:
            fingerprint = "sha256:" + hashlib.sha256(tree.encode("utf-8")).hexdigest()
    if fingerprint == "UNKNOWN" or not clean:
        fingerprint = _hash_scope(repo, scope, include_dirty_marker=not clean)

    payload = {
        "repository": name,
        "git_commit": commit if ok_commit else "UNKNOWN",
        "git_branch": branch if ok_branch else "UNKNOWN",
        "working_tree_clean": bool(clean),
        "source_fingerprint": fingerprint,
    }
    return SourceSnapshot(
        source_snapshot_id=content_id("SOURCE_SNAPSHOT", PROVENANCE_SCHEMA_VERSION, payload),
        repository=payload["repository"],
        git_commit=payload["git_commit"],
        git_branch=payload["git_branch"],
        working_tree_clean=payload["working_tree_clean"],
        source_fingerprint=payload["source_fingerprint"],
        schema_version=PROVENANCE_SCHEMA_VERSION,
    )


def _hash_scope(repo: Path, scope: list[str], include_dirty_marker: bool) -> str:
    digest = hashlib.sha256()
    entries: list[tuple[str, str, int]] = []
    for pattern in sorted(scope):
        base = repo / pattern
        candidates = sorted(base.rglob("*")) if base.is_dir() else [base]
        for path in candidates:
            if not path.is_file():
                continue
            try:
                content_hash, size = hash_file(path)
            except OSError:
                continue
            entries.append((str(path.relative_to(repo)).replace("\\", "/"), content_hash, size))
    for rel, content_hash, size in sorted(entries):
        digest.update(f"{rel}|{content_hash}|{size}\n".encode())
    if include_dirty_marker:
        digest.update(b"dirty-tree")
    return "sha256:" + digest.hexdigest()
