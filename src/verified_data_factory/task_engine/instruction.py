"""Instruction rendering (Phase 1).

Rule (ADR-005): the structured ``TaskInstance`` is the source of truth.
The instruction is a human/model-facing rendering of it, produced from
the template's ``instruction_template`` plus task parameters.
"""

from __future__ import annotations

from typing import Any

from .errors import InstructionError


def render_instruction(template_instruction: str, context: dict[str, Any]) -> str:
    """Render ``template_instruction`` with ``str.format`` over ``context``."""
    try:
        text = template_instruction.format(**context)
    except KeyError as exc:
        raise InstructionError(f"instruction template missing parameter: {exc}") from exc
    if not text.strip():
        raise InstructionError("rendered instruction is empty")
    return text


def build_instruction_context(
    *,
    tables: dict[str, list[dict[str, Any]]],
    requirements: dict[str, Any],
    edge_cases: list[str],
) -> dict[str, Any]:
    """Assemble the default rendering context from task data."""
    table_list = ", ".join(sorted(tables))
    context: dict[str, Any] = {
        "tables": table_list,
        "table_list": table_list,
        "edge_cases": ", ".join(edge_cases) if edge_cases else "none",
    }
    context.update(requirements)
    return context
