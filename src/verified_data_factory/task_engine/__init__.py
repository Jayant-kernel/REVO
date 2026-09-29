"""Task Engine public API (Phase 1).

Phase 2 consumers should program against ``api`` (``get_template``,
``list_templates``, ``generate_task``, ``generate_batch``,
``serialize_task``, ``deserialize_task``, ``recreate_task``,
``recreate_fixture``, ``validate_task``). Deeper imports (``fixtures``,
``canonical``, ``seed`` internals) are available but not contractual.
"""

from .api import (
    deserialize_task,
    get_template,
    list_templates,
    recreate_fixture,
    recreate_task,
    serialize_task,
)
from .canonical import canonical_hash, canonical_json, canonical_task_dict
from .errors import (
    FixtureError,
    InstructionError,
    RegistryError,
    TaskEngineError,
    TemplateError,
    ValidationError,
)
from .export import (
    read_jsonl,
    task_from_dict,
    task_from_json,
    task_to_dict,
    task_to_json,
    write_jsonl,
)
from .fixtures import materialize_duckdb, materialize_temp_duckdb
from .generator import generate_batch, generate_task
from .models import TaskInstance, TaskTemplate
from .registry import TemplateRegistry, load_builtin_registry
from .schema import ddl_for_schema, ddl_for_table
from .seed import ENGINE_VERSION
from .template import load_template_file, template_from_dict
from .validation import validate_task, validate_template

__all__ = [
    "ENGINE_VERSION",
    "FixtureError",
    "InstructionError",
    "RegistryError",
    "TaskEngineError",
    "TaskInstance",
    "TaskTemplate",
    "TemplateError",
    "TemplateRegistry",
    "ValidationError",
    "canonical_hash",
    "canonical_json",
    "canonical_task_dict",
    "ddl_for_schema",
    "ddl_for_table",
    "deserialize_task",
    "generate_batch",
    "generate_task",
    "get_template",
    "list_templates",
    "load_builtin_registry",
    "load_template_file",
    "materialize_duckdb",
    "materialize_temp_duckdb",
    "read_jsonl",
    "recreate_fixture",
    "recreate_task",
    "serialize_task",
    "task_from_dict",
    "task_from_json",
    "task_to_dict",
    "task_to_json",
    "template_from_dict",
    "validate_task",
    "validate_template",
    "write_jsonl",
]
