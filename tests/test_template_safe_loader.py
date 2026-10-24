"""Use the installed safe parser efficiently without changing DSL semantics."""
from pathlib import Path

import yaml

from verified_data_factory.task_engine.template import load_template_file, template_from_dict


def test_template_loader_prefers_available_safe_accelerator(monkeypatch):
    seen = []
    class InstrumentedSafeLoader(yaml.SafeLoader):
        def __init__(self, stream):
            seen.append(True)
            super().__init__(stream)
    monkeypatch.setattr(yaml, "CSafeLoader", InstrumentedSafeLoader, raising=False)
    load_template_file("templates/sql/funnel/saas_activation_payment.yaml")
    assert seen == [True]


def test_accelerated_loader_preserves_every_builtin_template():
    paths = list(Path("templates/sql").rglob("*.yaml"))
    assert paths
    for path in paths:
        pure = template_from_dict(yaml.safe_load(path.read_text(encoding="utf-8")))
        accelerated = load_template_file(path)
        assert accelerated == pure, str(path)
