"""Shared fixtures and helpers for Task Engine tests."""

from pathlib import Path

import pytest
import yaml

from verified_data_factory.task_engine import load_builtin_registry


@pytest.fixture(scope="session")
def registry():
    return load_builtin_registry()


def catalog_entries() -> list[dict]:
    """Parse configs/task_catalog.yaml (shared by catalog + identity tests)."""
    catalog = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "configs" / "task_catalog.yaml").read_text(
            encoding="utf-8"
        )
    )
    return catalog["templates"]
