"""Domain exceptions for the Task Engine (Phase 1)."""


class TaskEngineError(Exception):
    """Base error for all Task Engine failures."""


class TemplateError(TaskEngineError):
    """Raised when a task template is malformed or invalid."""


class RegistryError(TaskEngineError):
    """Raised for registry misuse (missing template, duplicates)."""


class ValidationError(TaskEngineError):
    """Raised when a template or task instance fails validation."""


class FixtureError(TaskEngineError):
    """Raised when fixture generation or materialization fails."""


class InstructionError(TaskEngineError):
    """Raised when instruction rendering fails."""
