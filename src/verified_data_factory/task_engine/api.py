"""Stable public API for Task Engine consumers (Phase 2+ entry points).

Everything here delegates to the engine modules; no generation logic lives
in this layer, and no internal RNG state or mutable state is exposed.
"""

from __future__ import annotations

from typing import Any

from .canonical import canonical_json
from .errors import TaskEngineError
from .export import task_from_json, task_to_json
from .fixtures import build_fixture_metadata, generate_fixture_tables
from .generator import generate_batch, generate_task
from .models import FixtureMetadata, TaskInstance, TaskTemplate
from .registry import TemplateRegistry
from .validation import validate_task

__all__ = [
    "deserialize_task",
    "generate_batch",
    "generate_task",
    "get_template",
    "list_templates",
    "recreate_fixture",
    "recreate_task",
    "serialize_task",
    "validate_task",
]


def get_template(
    registry: TemplateRegistry, template_id: str, version: int | None = None
) -> TaskTemplate:
    """Fetch a template by id (latest version unless pinned)."""
    return registry.get(template_id, version)


def list_templates(registry: TemplateRegistry, family: str | None = None) -> list[TaskTemplate]:
    """List templates, optionally filtered by family."""
    if family is not None:
        return registry.list_by_family(family)
    return registry.list()


def serialize_task(task: TaskInstance) -> str:
    """Serialize a task to stable JSON (external contract uses ``"schema"``)."""
    return task_to_json(task)


def deserialize_task(text: str) -> TaskInstance:
    """Reconstruct and validate a task from :func:`serialize_task` output."""
    task = task_from_json(text)
    validate_task(task)
    return task


def recreate_task(registry: TemplateRegistry, task: TaskInstance) -> TaskInstance:
    """Regenerate ``task`` from its stored (template, version, seed, config).

    Returns the regenerated instance after asserting canonical equality —
    the executable form of the seed-replay contract.
    """
    template = registry.get(task.template_id, task.template_version)
    again = generate_task(template, task.seed, dict(task.generation_metadata.config))
    if canonical_json(again) != canonical_json(task):
        raise TaskEngineError(f"seed-replay mismatch for {task.task_id}")
    return again


def recreate_fixture(
    template: TaskTemplate, seed: int
) -> tuple[dict[str, list[dict[str, Any]]], FixtureMetadata]:
    """Regenerate fixture rows + metadata without building an instruction.

    Lower-level than :func:`recreate_task`; useful for consumers that only
    need the database contents (e.g. materializing DuckDB fixtures).
    """
    tables, _ = generate_fixture_tables(template, seed)
    return tables, build_fixture_metadata(template, seed, tables)
