"""Prompt construction (Phase 2).

Data flow guard: :func:`build_solver_context` selects ONLY the public
solver-facing subset (instruction, dialect, DDL, explicit requirements).
``oracle_spec``, fixture rows, verification metadata, and internal
task-engine metadata can never reach the model through this module —
they are not even attributes of the context object.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from verified_data_factory.task_engine import ddl_for_schema
from verified_data_factory.task_engine.models import TaskInstance

from .models import PROMPT_VERSION, SQL_DIALECT


class SolverContext(BaseModel):
    """Everything the model may see. Nothing else."""

    model_config = {"frozen": True}

    task_id: str = Field(min_length=1)
    dialect: str = Field(min_length=1)
    ddl: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    requirements: dict[str, Any] = Field(default_factory=dict)
    prompt_version: str = Field(min_length=1)


def build_solver_context(task: TaskInstance) -> SolverContext:
    """Build the public solver context. The input task is never mutated."""
    ddl = "\n\n".join(ddl_for_schema(task.schema_) + [""])
    return SolverContext(
        task_id=task.task_id,
        dialect=SQL_DIALECT,
        ddl=ddl.strip(),
        instruction=task.instruction,
        requirements=dict(task.requirements),
        prompt_version=PROMPT_VERSION,
    )


def build_sql_prompt(task: TaskInstance) -> str:
    """Render a deterministic text-to-SQL prompt for ``task``."""
    ctx = build_solver_context(task)
    return (
        "You are an expert SQL programmer. Write a single correct SQL query\n"
        f"in the {ctx.dialect} SQL dialect for the task below.\n"
        "\n"
        "Schema:\n"
        "\n"
        f"{ctx.ddl}\n"
        "\n"
        "Task:\n"
        "\n"
        f"{ctx.instruction}\n"
        "\n"
        "Public output contract (these requirements are binding):\n"
        "\n"
        f"{json.dumps(ctx.requirements, sort_keys=True)}\n"
        "\n"
        "Return only the SQL query. Do not return Markdown fences,\n"
        "explanations, comments, or analysis."
    )
