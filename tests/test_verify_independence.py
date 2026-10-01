"""Oracle independence tests: structural, not disciplinary.

The oracle must be computable from (requirements, fixture rows) alone.
These tests fail the build if oracle code ever reaches for candidate
text, execution output, model metadata, or a database engine.
"""

import inspect
from pathlib import Path

import pytest

import verified_data_factory.verification.oracle as oracle_mod
from verified_data_factory.verification import oracle_registry
from verified_data_factory.verification.errors import OracleUnknownError

FORBIDDEN_IDENTIFIERS = (
    "candidate_sql",
    "raw_response",
    "CandidateSolution",
    "ExecutionResult",
    "generation_config",
    "model_revision",
    "provider_metadata",
    "result_data",
    "finish_reason",
    "stdout",
    "stderr",
)

FORBIDDEN_ENGINE_CALLS = ("import duckdb", "sqlite3", "sqlglot", ".execute(")


def _oracle_source():
    return Path(oracle_mod.__file__).read_text(encoding="utf-8")


def test_oracle_source_references_no_candidate_concepts():
    source = _oracle_source()
    for identifier in FORBIDDEN_IDENTIFIERS:
        assert identifier not in source, identifier


def test_oracle_never_touches_a_database():
    source = _oracle_source()
    for fragment in FORBIDDEN_ENGINE_CALLS:
        assert fragment not in source, fragment


def test_oracle_signatures_take_only_requirements_and_rows():
    fns = [
        member
        for name, member in inspect.getmembers(oracle_mod, inspect.isfunction)
        if name.startswith("oracle_")
    ]
    assert len(fns) == 14
    for fn in fns:
        params = list(inspect.signature(fn).parameters)
        assert params == ["requirements", "tables"], (fn.__name__, params)


def test_registry_covers_frozen_templates_only():
    """The versioned template registry contract, stated explicitly.

    - Every builtin template version resolves to an oracle (no gaps).
    - Every oracle entry is either a current builtin version or an
      explicitly retired historical version (nothing silent).
    - Retired versions are not generatable (absent from the registry).
    - Retired versions remain resolvable for historical replay.
    """
    from verified_data_factory.task_engine import load_builtin_registry
    from verified_data_factory.task_engine.errors import RegistryError
    from verified_data_factory.verification import is_retired_version

    registry = load_builtin_registry()
    template_keys = {(t.template_id, t.version) for t in registry.list()}
    oracle_keys = set(oracle_registry.ORACLES)

    # No gaps: every generatable template verifies.
    assert template_keys <= oracle_keys
    # Nothing silent: every oracle is current or explicitly retired.
    assert oracle_keys <= template_keys | oracle_registry.RETIRED_VERSIONS
    # Retired versions cannot be generated...
    for template_id, version in sorted(oracle_registry.RETIRED_VERSIONS):
        try:
            registry.get(template_id, version)
        except RegistryError:
            pass
        else:
            raise AssertionError(
                f"retired version unexpectedly generatable: {(template_id, version)}"
            )
        # ...but stay resolvable for historical records.
        assert is_retired_version(template_id, version)
        oracle_registry.get_oracle(template_id, version)
    # Unknown versions raise on both sides.
    with pytest.raises(RegistryError):
        registry.get("sql.joins.simple", 999)
    with pytest.raises(OracleUnknownError):
        oracle_registry.get_oracle("sql.joins.simple", 999)


def test_frozen_template_set_is_explicit():
    """The current generatable set is pinned: additions/removals must update this test."""
    from verified_data_factory.task_engine import load_builtin_registry

    registry = load_builtin_registry()
    assert {(t.template_id, t.version) for t in registry.list()} == {
        ("sql.aggregation.grouped", 2),
        ("sql.aggregation.payment_net_settled", 1),
            ("sql.aggregation.support_sla_breaches", 1),
        ("sql.cte.monthly", 2),
        ("sql.cte.monthly", 3),
        ("sql.cte.monthly", 4),
            ("sql.dedup.latest", 2),
            ("sql.dedup.education_grade_revisions", 1),
            ("sql.funnel.completion", 2),
            ("sql.funnel.completion", 3),
        ("sql.joins.multi", 1),
        ("sql.joins.simple", 1),
        ("sql.joins.saas_paid_invoices", 1),
            ("sql.retention.30_day", 1),
            ("sql.retention.30_day", 2),
        ("sql.subqueries.exists", 1),
        ("sql.subqueries.exists", 2),
        ("sql.temporal.monthly", 2),
        ("sql.temporal.monthly", 3),
        ("sql.temporal.monthly", 4),
        ("sql.temporal.monthly", 5),
            ("sql.windows.ranked", 1),
            ("sql.windows.ranked", 2),
    }


def test_verifier_never_executes_sql_outside_phase3():
    package = Path(oracle_mod.__file__).parent
    for path in package.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "import duckdb" not in source, path.name
        assert "sqlite3" not in source, path.name
    # The only execution path is the injected backend (Phase 3 in production).
    import verified_data_factory.verification.verifier as verifier_mod

    source = Path(verifier_mod.__file__).read_text(encoding="utf-8")
    assert "execute_on_rows" not in source  # verifier stages rows; backend executes
    assert "SandboxExecutor" not in source


def test_no_llm_judge_anywhere():
    package = Path(oracle_mod.__file__).parent
    for path in package.glob("*.py"):
        lowered = path.read_text(encoding="utf-8").lower()
        for banned in ("openai", "anthropic", "gemini", "llm_judge", "llm-as-judge", "judge_model"):
            assert banned not in lowered, (path.name, banned)
