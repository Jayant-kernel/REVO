"""Template registry (Phase 1).

No ``if/elif`` chains: templates self-register by ``(template_id, version)``
and are discoverable by family. Adding a template = adding a YAML file.
"""

from __future__ import annotations

from pathlib import Path

from .errors import RegistryError, TemplateError
from .models import TaskTemplate
from .template import load_template_file

# Alias: the `list` method below shadows the builtin inside the class body,
# so annotations use this module-level name to keep meaning `builtins.list`.
_TemplateList = list


class TemplateRegistry:
    """In-memory registry of validated task templates."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, int], TaskTemplate] = {}

    def register(self, template: TaskTemplate) -> None:
        key = (template.template_id, template.version)
        if key in self._by_key:
            raise RegistryError(f"duplicate template {key}")
        self._by_key[key] = template

    def load_file(self, path: str | Path) -> TaskTemplate:
        template = load_template_file(path)
        self.register(template)
        return template

    def load_directory(self, directory: str | Path) -> int:
        directory = Path(directory)
        if not directory.is_dir():
            raise RegistryError(f"not a directory: {directory}")
        seen: set[Path] = set()
        for pattern in ("*.yaml", "*.yml"):
            for path in sorted(directory.rglob(pattern)):
                if path in seen:
                    continue
                seen.add(path)
                self.load_file(path)
        return len(seen)

    def get(self, template_id: str, version: int | None = None) -> TaskTemplate:
        """Fetch a template; latest version wins when ``version`` is None."""
        candidates = [t for (tid, _), t in self._by_key.items() if tid == template_id]
        if not candidates:
            raise RegistryError(f"unknown template: {template_id!r}")
        if version is not None:
            for t in candidates:
                if t.version == version:
                    return t
            raise RegistryError(f"unknown version {version} for {template_id!r}")
        return max(candidates, key=lambda t: t.version)

    def list(self) -> _TemplateList[TaskTemplate]:
        return sorted(self._by_key.values(), key=lambda t: (t.template_id, t.version))

    def list_by_family(self, family: str) -> _TemplateList[TaskTemplate]:
        return [t for t in self.list() if t.family == family]

    def metadata(self) -> _TemplateList[dict[str, object]]:
        return [
            {
                "template_id": t.template_id,
                "version": t.version,
                "family": t.family,
                "difficulty": t.difficulty,
                "description": t.description,
            }
            for t in self.list()
        ]

    def __len__(self) -> int:
        return len(self._by_key)


def load_builtin_registry(templates_root: str | Path | None = None) -> TemplateRegistry:
    """Load all YAML templates shipped under ``templates/sql/``."""
    root = (
        Path(templates_root)
        if templates_root
        else Path(__file__).resolve().parents[3] / "templates" / "sql"
    )
    registry = TemplateRegistry()
    if not root.is_dir():
        raise RegistryError(f"builtin templates directory missing: {root}")
    seen: set[Path] = set()
    for pattern in ("*.yaml", "*.yml"):
        for path in sorted(root.rglob(pattern)):
            if path in seen:
                continue
            seen.add(path)
            try:
                registry.load_file(path)
            except TemplateError as exc:
                raise RegistryError(f"malformed builtin template {path}: {exc}") from exc
    if len(registry) == 0:
        raise RegistryError(f"no templates found under {root}")
    return registry
