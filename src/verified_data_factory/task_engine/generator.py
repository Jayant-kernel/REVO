"""Task generation orchestration (Phase 1).

Pure, stateless functions: ``generate_task(template, seed, config)`` is the
single entry point later layers (Generation, Verification) will consume.
"""

from __future__ import annotations

import logging
from typing import Any

from .fixtures import build_fixture_metadata, generate_fixture_tables
from .instruction import build_instruction_context, render_instruction
from .models import GenerationMetadata, TaskInstance
from .seed import ENGINE_VERSION, build_task_id
from .validation import validate_task

logger = logging.getLogger(__name__)

# Import only for typing to avoid a hard circular import at module load.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import TaskTemplate


def generate_task(
    template: TaskTemplate,
    seed: int,
    config_override: dict[str, Any] | None = None,
) -> TaskInstance:
    """Instantiate ``template`` with ``seed`` into a validated TaskInstance."""
    if seed < 0:
        raise ValueError("seed must be non-negative")
    config: dict[str, Any] = dict(template.generation_config)
    if config_override:
        config.update(config_override)

    tables, ensured_edges = generate_fixture_tables(template, seed)
    fixture_metadata = build_fixture_metadata(template, seed, tables)
    # Canonical ordering (sorted tables, sorted edge cases) so model-level
    # round-trips are stable: table order carries no task semantics.
    tables = dict(sorted(tables.items()))
    ensured_edges = sorted(ensured_edges)
    schema = sorted(template.schema_definition, key=lambda t: t.name)

    requirements = dict(template.requirements)
    context = build_instruction_context(
        tables=tables, requirements=requirements, edge_cases=ensured_edges
    )
    instruction = render_instruction(template.instruction_template, context)

    task = TaskInstance(
        task_id=build_task_id(template.template_id, template.version, seed, config, ENGINE_VERSION),
        template_id=template.template_id,
        template_version=template.version,
        seed=seed,
        family=template.family,
        difficulty=template.difficulty,
        instruction=instruction,
        schema_=schema,
        tables=tables,
        fixture_metadata=fixture_metadata,
        requirements=requirements,
        constraints=dict(config.get("constraints", {})),
        edge_cases=ensured_edges,
        oracle_spec=template.oracle_spec,
        generation_metadata=GenerationMetadata(engine_version=ENGINE_VERSION, config=config),
    )
    validate_task(task)
    logger.info(
        "generated task",
        extra={
            "template_id": template.template_id,
            "template_version": template.version,
            "seed": seed,
            "task_id": task.task_id,
        },
    )
    return task


def generate_batch(
    template: TaskTemplate, seeds: list[int], config_override: dict[str, Any] | None = None
) -> list[TaskInstance]:
    """Generate one task per seed (parallelizable: no shared mutable state)."""
    return [generate_task(template, s, config_override) for s in seeds]
