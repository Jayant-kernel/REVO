"""Phase 0-8 structural tests.

``task_engine`` (1), ``generation`` (2), ``sandbox`` (3), ``verification``
(4), ``quality`` (5), ``provenance`` (6), ``products`` (7), and
``business`` (8) are expected; later modules must NOT exist.
"""

import importlib
import pathlib


def test_package_imports() -> None:
    import verified_data_factory

    assert verified_data_factory.__version__ == "0.8.0"


def test_no_premature_pipeline_modules() -> None:
    # Phase 7+ modules. Earlier layers are intentionally present.
    premature = [
        "verified_data_factory.datasets",
    ]
    for name in premature:
        try:
            importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        raise AssertionError(f"Premature module {name!r} exists in Phase 0")


def test_required_docs_exist() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    required = [
        "docs/architecture.md",
        "docs/roadmap.md",
        "docs/technical-stack.md",
        "docs/data-model.md",
        "docs/golden-record.md",
        "docs/verification-principles.md",
        "docs/security.md",
        "docs/licensing.md",
        "docs/metrics.md",
        "docs/first-experiment.md",
        "docs/business-validation.md",
        "docs/definition-of-done.md",
        "docs/phase-1-contract.md",
        "docs/phase-2-generation.md",
        "docs/phase-3-sandbox.md",
        "docs/phase-3-4-integration.md",
        "docs/phase-4-verification.md",
        "docs/phase-5-quality.md",
        "docs/quality-metrics.md",
        "docs/golden-selection.md",
        "docs/audit.md",
        "docs/phase-6-provenance.md",
        "docs/provenance-model.md",
        "docs/reproducibility.md",
        "docs/provenance-bundle.md",
        "docs/phase-7-products.md",
        "docs/product-model.md",
        "docs/splits.md",
        "docs/release-format.md",
        "docs/consuming-products.md",
        "docs/phase-8-business.md",
        "docs/experiments.md",
        "docs/model-value.md",
        "docs/customer-validation.md",
        "docs/economics.md",
        "docs/gtm/positioning.md",
        "docs/gtm/target-customer.md",
        "docs/gtm/use-cases.md",
        "docs/gtm/product-one-pager.md",
        "docs/gtm/pilot-template.md",
        "docs/gtm/technical-datasheet.md",
        "docs/gtm/faq.md",
        "docs/gtm/objections.md",
        "docs/roadmap-evidence.json",
    ]
    missing = [p for p in required if not (root / p).is_file()]
    assert not missing, f"Missing Phase 0 docs: {missing}"
