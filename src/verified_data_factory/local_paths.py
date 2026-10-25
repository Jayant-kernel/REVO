"""Windows extended-length IO paths without changing filesystem policy."""
from __future__ import annotations

import os
from pathlib import Path


def io_path(path: Path) -> Path:
    if os.name != "nt":
        return path
    value = str(path.absolute())
    if value.startswith("\\\\?\\"):
        return path
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value[2:])
    return Path("\\\\?\\" + value)
