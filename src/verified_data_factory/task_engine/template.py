"""YAML Task DSL loader (Phase 1).

The DSL is deliberately small: human-readable, versionable, deterministic,
validated with Pydantic. Only concepts needed by the 10 Phase 1 families
are supported.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import TemplateError
from .models import OracleSpec, TableDefinition, TaskTemplate
from .validation import validate_template

REQUIRED_TOP_LEVEL = {
    "template_id",
    "version",
    "family",
    "description",
    "difficulty",
    "tables",
    "oracle",
    "instruction_template",
}


def _parse_tables(raw: Any) -> list[TableDefinition]:
    if isinstance(raw, dict):
        items = [{"name": name, **spec} for name, spec in raw.items()]
    elif isinstance(raw, list):
        items = raw
    else:
        raise TemplateError("'tables' must be a mapping or a list")
    try:
        return [TableDefinition.model_validate(t) for t in items]
    except Exception as exc:
        raise TemplateError(f"invalid table definitions: {exc}") from exc


def template_from_dict(data: dict[str, Any]) -> TaskTemplate:
    """Build and validate a TaskTemplate from a parsed YAML mapping."""
    missing = REQUIRED_TOP_LEVEL - set(data)
    if missing:
        raise TemplateError(f"missing required fields: {sorted(missing)}")
    try:
        template = TaskTemplate(
            template_id=data["template_id"],
            version=int(data["version"]),
            family=data["family"],
            description=data["description"],
            difficulty=data["difficulty"],
            schema_definition=_parse_tables(data["tables"]),
            generation_config=dict(data.get("generation_config", {})),
            requirements=dict(data.get("requirements", {})),
            edge_cases=list(data.get("edge_cases", [])),
            oracle_spec=OracleSpec.model_validate(data["oracle"]),
            instruction_template=data["instruction_template"],
        )
    except TemplateError:
        raise
    except Exception as exc:
        raise TemplateError(f"invalid template: {exc}") from exc
    validate_template(template)
    return template


def load_template_file(path: str | Path) -> TaskTemplate:
    """Load a single YAML template file."""
    path = Path(path)
    try:
        loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=loader)
    except Exception as exc:
        raise TemplateError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise TemplateError(f"template {path} must be a YAML mapping")
    try:
        return template_from_dict(data)
    except TemplateError as exc:
        raise TemplateError(f"{path}: {exc}") from exc
